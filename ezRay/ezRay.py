## Dependencies:
import json
import time
import webbrowser
from typing import Any, Callable, Dict, List, NoReturn, Optional, Tuple, Union

import psutil
import ray

# typing
import ray.remote_function
import ray.runtime_context

# context aware progress bar
# detect jupyter notebook
from IPython import get_ipython

try:
    ipy_str = str(type(get_ipython()))
    if 'zmqshell' in ipy_str:
        from tqdm.notebook import tqdm
    else:
        from tqdm import tqdm
except:
    from tqdm import tqdm

#%% Multi Core Execution Main
class MultiCoreExecutionTool:
    RuntimeData:Dict[int,Dict[str,Any]]
    RuntimeResults:Dict[int,Any]
    
    runimte_context:ray.runtime_context.RuntimeContext
    runtime_metadata:Dict[str,Union[str, bool, int, float]]
    dashboard_url:str
    
    silent:bool
    DEBUG:bool

    def __init__(self, RuntimeData:Any = None, /, **kwargs):
        ## Default Verbosity
        self.silent = False
        self.DEBUG = False
        
        ## Initialize attributes
        self.dashboard_url = None
        self.runtime_context = None
        self.runtime_metadata = None
        self.RuntimeResults = None

        ## Setattributes
        for key, value in kwargs.items():
            setattr(self, key, value)

        ## set the debug flag
        if 'DEBUG' in kwargs.keys():
            self.DEBUG = kwargs['DEBUG']
            self.silent = False

        self.__post_init__(RuntimeData, **kwargs)

    def __post_init__(self, RuntimeData:Any, /, **kwargs)->NoReturn:
        self.__metatada_init__(**kwargs)
        self.__initialize__(num_cpu = self.runtime_metadata['num_cpu'],
                            num_gpu = self.runtime_metadata['num_gpu'],
                            launch_dashboard = self.runtime_metadata['launch_dashboard'])
        self.__offload_on_init__(RuntimeData)
        return None

    def __metatada_init__(self,**kwargs):
        ## Default Metadata
        self.runtime_metadata = {'num_cpu': 1,
                                 'num_gpu': 0,
                                 'launch_dashboard': False,
                                 'sleeptime': 0.1}
        # update metadata with given values
        self.runtime_metadata.update(kwargs)
        
        return None
    
    def __offload_on_init__(self, RuntimeData:Any)->NoReturn:
        ## This has to be called AFTER the ray is initialized
        # otherwise, a new ray object will be created and the object references will be unreachable from within the main ray object.
        
        if RuntimeData is None:
            print('No Runtime Data provided. Use the "update()" method to update the Runtime Data prior to running methods.')
            return None
        
        ## Set RuntimeData
        self.RuntimeData = RuntimeData if RuntimeData is not None else None
        self.RuntimeData_ref = self.__offload_data__() if RuntimeData is not None else None
        
        return None
        
#%% Class methods
    @classmethod
    def from_dict(cls, data:Dict[str,Any])->'MultiCoreExecutionTool':
        return cls(**data)
    
    @classmethod
    def from_json(cls, path:str)->'MultiCoreExecutionTool':
        with open(path, 'r') as file:
            data = json.load(file)
        return cls(**data)
    
#%% DEBUG & DEMO
    @ray.remote
    def test_function(kwargs)->Dict[Any,Any]:
        """Test function for the framework that merely forwards the input."""
        return {k:v for k,v in kwargs.items()}
    
#%% Ray Wrapper
    @ray.remote
    def __method_wrapper__(method:Callable, input:Dict[Any,Any])->ray.remote_function.RemoteFunction:
        """Ray wrapper for arbitrary function logic.

        Args:
            method (Callable): Arbitrary method that takes at least one input.
            input (Dict[Any,Any]): Method input that will be forwarded to the main logic.

        Returns:
            Callable: Returns a ray.remote callable object.
        """
        return method(**input)
        
#%% Main Backend   
    def __run__(self, worker:Union[Callable, ray.remote_function.RemoteFunction])->bool: 
           
        ## check if ray is initialized
        if not ray.is_initialized():
            raise Exception('Ray is not initialized. Use object.initialize() to initialize Ray.')
        
        if not self.is_ray_compatible(worker):
            try:
                subLogic = worker
                worker = self.__method_wrapper__
            except Exception as e:
                print(f'Error: {e}')
                return False
        
        ## prepare schedule
        schedule = self.__setup_schedule__()
        if len(schedule) == 0:
            print('No pending tasks to run.')
            return True
        
        ## workflow factory
        if self.silent:
            permision, states = self.__multicore_workflow__(worker = worker,
                                                            schedule = schedule,
                                                            listener = self.__silent_listener__,
                                                            scheduler = self.__silent_scheduler__,
                                                            subLogic = subLogic if 'subLogic' in locals() else None)
        else:
            permision, states = self.__multicore_workflow__(worker = worker,
                                                            schedule = schedule,
                                                            listener = self.__verbose_listener__,
                                                            scheduler = self.__verbose_scheduler__,
                                                            subLogic = subLogic if 'subLogic' in locals() else None)
            
        ## update the results
        if permision:
            for k in schedule:
                self.RuntimeResults[k].update({'result':states[k], 'status':'completed'})
        
        return permision 
 
    def __verbose_scheduler__(self, 
                              worker:ray.remote_function.RemoteFunction,
                              schedule:List[Any],
                              subLogic:Optional[Callable])->Dict[ray.ObjectRef,int]:
        
        ## VERBOSE MODE
        # schedule the workers and return the object references
        
        # if subLogic is provided, pass it to the wrapper
        if subLogic is not None:
            return {worker.remote(subLogic, self.RuntimeData_ref[schedule_index]):schedule_index
                    for schedule_index in tqdm(schedule, total=len(schedule), desc="Scheduling Workers", position = 0)}
        
        # if a ray compatible worker is provided, forward the worker directly
        return {worker.remote(self.RuntimeData_ref[schedule_index]):schedule_index
                for schedule_index in tqdm(schedule, total=len(schedule), desc="Scheduling Workers", position = 0)}
    
    def __silent_scheduler__(self, 
                             worker:ray.remote_function.RemoteFunction,
                             schedule:List,
                             subLogic:Optional[Callable])->Dict[ray.ObjectRef,int]:
        ## SILENT MODE
        # schedule the workers and return the object references
        
        # if subLogic is provided, pass it to the wrapper
        if subLogic is not None:
            return {worker.remote(subLogic, self.RuntimeData_ref[schedule_index]):schedule_index
                    for schedule_index in schedule}
        
        # if a ray compatible worker is provided, forward the worker directly
        return {worker.remote(self.RuntimeData_ref[schedule_index]):schedule_index
                for schedule_index in schedule}
        
    def __multicore_workflow__(self,
                               worker:Union[Callable, ray.remote_function.RemoteFunction],
                               schedule:List[Any],
                               listener:Callable,
                               scheduler:Callable,
                               subLogic:Optional[Callable]
                               )->Tuple[bool, Dict[int,Any]]:    
        
        ## workflow and listening
        permission, finished_states = listener(scheduler(worker, schedule, subLogic))
                
        ## check completion
        if permission:
            self.RuntimeResults | {k:{'result':v, 'status':'completed'} for k,v in finished_states.items()}
                
            ## Shutdown Ray
            if self.DEBUG:
                print("Multi Core Execution Complete...")
                print("Use 'OverlayGenerator.shutdown_multi_core()' to shutdown the cluster.")
            
            return True, finished_states
        
        return False, None
#%% Process Listener
    def __silent_listener__(self, object_references:Dict[ray.ObjectRef,int])->Tuple[bool, Dict[int,Any]]:      
        try:
            # setup collection list
            pending_states:list = list(object_references.keys())
            finished_states:list = []
            
            if self.DEBUG:
                print('Listening to Ray Progress...')
                
            while len(pending_states) > 0:
                try:
                    # get the ready refs
                    finished, pending_states = ray.wait(
                        pending_states, timeout=8.0
                    )
                    
                    finished_states.extend(finished)
                    
                except KeyboardInterrupt:
                    print('Interrupted')
                    break
                
                if self.runtime_metadata['sleeptime'] > 0:
                    time.sleep(self.runtime_metadata['sleeptime'])
            
            # sort and return the results
            finished_states = {object_references[ref]:ray.get(ref) for ref in finished_states}
            
            return True, finished_states
        
        except Exception as e:
            print(f'Error: {e}')
            return False, None

    def __verbose_listener__(self, object_references:Dict[ray.ObjectRef,int])->Tuple[bool, Dict[int,Any]]:
        
        try:
            if self.DEBUG:
                print('Setting up progress monitors...')
                
            ## create progress monitors
            core_progress = tqdm(total = len(object_references), desc = 'Workers', position = 1)
            cpu_progress = tqdm(total = 100, desc="CPU usage", bar_format='{desc}: {percentage:3.0f}%|{bar}|', position = 2)
            mem_progress = tqdm(total=psutil.virtual_memory().total, desc="RAM usage", bar_format='{desc}: {percentage:3.0f}%|{bar}|', position = 3)
            
            # setup collection list
            pending_states:list = list(object_references.keys())
            finished_states:list = []
            
            if self.DEBUG:
                print('Listening to Ray Progress...')
            ## listen for progress
            while len(pending_states) > 0:
                try:
                    # get the ready refs
                    finished, pending_states = ray.wait(
                        pending_states, timeout=8.0
                    )
                    
                    finished_states.extend(finished)
                    
                    # update the progress bars
                    mem_progress.n = psutil.virtual_memory().used
                    mem_progress.refresh()
                    
                    cpu_progress.n = psutil.cpu_percent()
                    cpu_progress.refresh()
                    
                    # update the progress bar
                    core_progress.n = len(finished_states)
                    core_progress.refresh()
                
                    # sleep for a bit
                    if self.runtime_metadata['sleeptime'] > 0:
                        time.sleep(self.runtime_metadata['sleeptime'])
                    
                except KeyboardInterrupt:
                    print('Interrupted')
                    break
            
            # set the progress bars to success
            core_progress.colour = 'green'
            cpu_progress.colour = 'green'
            mem_progress.colour = 'green'
            
            # set the progress bars to their final values
            core_progress.n = len(object_references)
            cpu_progress.n = 0
            mem_progress.n = 0
            
            # close the progress bars
            core_progress.close()
            cpu_progress.close()
            mem_progress.close()
            
            # sort and return the results
            finished_states = {object_references[ref]:ray.get(ref) for ref in finished_states}
            
            if self.DEBUG:
                print('Ray Progress Complete...')
            
            return True, finished_states
        
        except Exception as e:
            print(f'Error: {e}')
            return False, None

##### API #####
#%% Main Execution
    def run(self, worker:Union[Callable, ray.remote_function.RemoteFunction])->bool:
        try:
            permission:bool = self.__run__(worker)
            assert permission
            
            if self.DEBUG:
                print('Multi Core Execution Complete...')
                print('Use "OverlayGenerator.get_results()" to get the results.')
            
            return True
        except Exception as e:
            print(f'Error: {e}')
            return False

#%% Runtime Control 
    def initialize(self, **kwargs)->NoReturn:
        try:
            init_instructions = self.runtime_metadata | kwargs
        except Exception as e:
            print(f'Error: {e}')
            return None
        
        self.__initialize__(num_cpu = init_instructions['num_cpu'],
                            num_gpu = init_instructions['num_gpu'],
                            launch_dashboard = init_instructions['launch_dashboard'])
    def shutdown(self)->NoReturn:
        self.__shutdown__()
    def reset(self, **kwargs)->NoReturn:
        self.__reset__(**kwargs)
    def reboot(self, **kwargs)->NoReturn:
        self.__reboot__(**kwargs)

#%% Runtime Data Control
    def update_data(self, RuntimeData:Any)->NoReturn:
        self.__update_data__(RuntimeData)

#%% Runtime Handling Backend
    def __initialize__(self,
                       num_cpu:int,
                       num_gpu:int,
                       launch_dashboard:bool
                       )->NoReturn:
    
        if self.DEBUG:
            print('Setting up Ray...')
        
        # shutdown any stray ray instances
        ray.shutdown()
        
        # ray init
        cluster_context = ray.init(num_cpus = num_cpu, 
                                   num_gpus = num_gpu,
                                   ignore_reinit_error=True)
        self.dashboard_url = f"http://{cluster_context.dashboard_url}"

        # dashboard
        if launch_dashboard:
            try:
                webbrowser.get('windows-default').open(self.dashboard_url,
                                                       autoraise = True,
                                                       new = 2)
            except Exception as e:
                print(f'Error: {e}')
        
        if self.DEBUG:
            print('Ray setup complete...')
            print(f'Ray Dashboard: {self.dashboard_url}')
        
        # set the runtime context
        self.runimte_context = cluster_context
    
    def __shutdown__(self)->NoReturn:
        if self.DEBUG:
            print('Shutting down Ray...')
        ray.shutdown()
        
    def __reset__(self, **kwargs)->NoReturn:
        self.RuntimeData_ref = None
        self.__metatada_init__(**kwargs)
         
    def __reboot__(self, **kwargs)->NoReturn:
        init_instructions = self.runtime_metadata | kwargs
        try:
            self.__shutdown__()
            self.__initialize__(num_cpu=init_instructions['num_cpu'],
                                num_gpu=init_instructions['num_gpu'],
                                launch_dashboard=init_instructions['launch_dashboard'])
        except Exception as e:
            print(f'Error: {e}')

#%% Runtime Data Handling
    def __setup_schedule__(self)->NoReturn:
        self.RuntimeResults = {k:{'result':None, 'status':'pending'} for k in self.RuntimeData.keys()}
        return [k for k,v in self.RuntimeResults.items() if v['status'] == 'pending']

    def __update_data__(self, RuntimeData:Dict[int,Dict[str,Any]])->NoReturn:
        self.RuntimeData = RuntimeData
        self.RuntimeData_ref = self.__offload_data__()
        self.__setup_schedule__()
        
    def __offload_data__(self)->Dict[int,ray.ObjectRef]:
        if self.DEBUG:
            print('Offloading data to Ray...')
        return {k:ray.put(v) for k,v in self.RuntimeData.items()}

#%% Helper
    def is_ray_compatible(self, func:Callable)->bool:
        if isinstance(func, ray.remote_function.RemoteFunction):
            return True
        return False 
    
    def is_initalized(self)->bool:
        if self.DEBUG:
            print('Checking Ray Status...')
        return ray.is_initialized()
    
    def get_results(self)->Dict[Any,Dict[Any,Any]]:
        if self.DEBUG:
            print('Fetching Results...')
        
        if self.RuntimeResults is None:
            print('No results found. Use the "run()" method to get results.')
            return None
        return self.RuntimeResults
