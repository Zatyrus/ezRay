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
except Exception as _:
    from tqdm import tqdm

#%% Multi Core Execution Main
class MultiCoreExecutionTool:
    RuntimeData:Dict[Any,Dict[Any,Any]]
    
    RuntimeResults:Dict[Any,Dict[str,Any]]
    RuntimeContext:ray.runtime_context.RuntimeContext
    RuntimeMetadata:Dict[str,Union[str, bool, int, float]]
    DashboardURL:str
    
    ListenerSleeptime:float
    AutoLaunchDashboard:bool
    silent:bool
    DEBUG:bool

    def __init__(self, RuntimeData:Dict[Any,Dict[Any,Any]] = None, /, **kwargs)->'MultiCoreExecutionTool':
        """Constructor for the MultiCoreExecutionTool class.

        Args:
            RuntimeData (Dict[Any,Dict[Any,Any]], optional): Dictionary containing keyword arguments for the methods to run. Defaults to None.

        Returns:
            MultiCoreExecutionTool: MultiCoreExecutionTool object.
        """
        ## Default Verbosity
        self.ListenerSleeptime = 0.1
        self.AutoLaunchDashboard = False
        self.silent = False
        self.DEBUG = False
        
        ## Initialize attributes
        self.DashboardURL = None
        self.RuntimeContext = None
        self.RuntimeMetadata = None
        self.RuntimeResults = None

        ## Setattributes
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        ## set the debug flag
        if 'DEBUG' in kwargs.keys():
            self.DEBUG = kwargs['DEBUG']
            self.silent = False

        self.__post_init__(RuntimeData, **kwargs)

    def __post_init__(self, RuntimeData:Dict[Any,Dict[Any,Any]], /, **kwargs)->NoReturn:
        """Post initialization method for the MultiCoreExecutionTool class. Handles routine initialization tasks.

        Args:
            RuntimeData (Dict[Any,Dict[Any,Any]]): Structured data to be processed by the methods.

        Returns:
            NoReturn: No Return
        """
        self.__initialize_metadata__(**kwargs)
        self.__initialize_ray_cluster__()
        self.__offload_on_init__(RuntimeData)

#%% Class methods
    @classmethod
    def from_dict(cls, data:Dict[str,Any])->'MultiCoreExecutionTool':
        """Convenience method to create a MultiCoreExecutionTool object from a dictionary.

        Returns:
            MultiCoreExecutionTool: MultiCoreExecutionTool object.
        """
        return cls(**data)
    
    @classmethod
    def from_json(cls, path:str)->'MultiCoreExecutionTool':
        """Convenience method to create a MultiCoreExecutionTool object from a JSON file.

        Args:
            path (str): Path to the JSON file.

        Returns:
            MultiCoreExecutionTool: MultiCoreExecutionTool object.
        """
        with open(path, 'r') as file:
            data = json.load(file)
        return cls(**data)
    
#%% DEBUG & DEMO
    @ray.remote(num_cpus=1, num_returns=1)
    def test_function(kwargs)->Dict[Any,Any]:
        """Test function for the framework that merely forwards the input."""
        return {k:v for k,v in kwargs.items()}
    
#%% Ray Wrapper
    def __setup_wrapper__(self)->Callable:
        @ray.remote(**self.RuntimeMetadata['task_metadata'])
        def __method_wrapper__(method:Callable, input:Dict[Any,Any])->ray.remote_function.RemoteFunction:
            """Ray wrapper for arbitrary function logic.

            Args:
                method (Callable): Arbitrary method that takes at least one input.
                input (Dict[Any,Any]): Method input that will be forwarded to the main logic.

            Returns:
                Callable: Returns a ray.remote callable object.
            """
            return method(**input)
        return __method_wrapper__
        
#%% Main Backend   
    def __run__(self, worker:Union[Callable, ray.remote_function.RemoteFunction])->bool: 
        """Main execution method for the MultiCoreExecutionTool class. Runs the provided worker on the provided data.

        Args:
            worker (Union[Callable, ray.remote_function.RemoteFunction]): Main worker or logic. Can be either ray.remote or a callable.

        Raises:
            Exception: Exception is raised if the core logic is not ray compatible.

        Returns:
            bool: Boolean flag that is True if the execution is successful.
        """
        ## check if ray is initialized
        if not ray.is_initialized():
            raise Exception('Ray is not initialized. Use object.initialize() to initialize Ray.')
        
        if not self.is_ray_compatible(worker):
            try:
                coreLogic = worker
                worker = self.__setup_wrapper__()
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
                                                            coreLogic = coreLogic if 'coreLogic' in locals() else None)
        else:
            permision, states = self.__multicore_workflow__(worker = worker,
                                                            schedule = schedule,
                                                            listener = self.__verbose_listener__,
                                                            scheduler = self.__verbose_scheduler__,
                                                            coreLogic = coreLogic if 'coreLogic' in locals() else None)
            
        ## update the results
        if permision:
            for k in schedule:
                self.RuntimeResults[k].update({'result':states[k], 'status':'completed'})
        
        return permision 
 
    def __verbose_scheduler__(self, 
                              worker:ray.remote_function.RemoteFunction,
                              schedule:List[Any],
                              coreLogic:Optional[Callable])->Dict[ray.ObjectRef,int]:
        """Verbose scheduler that handles remote task execution.

        Args:
            worker (ray.remote_function.RemoteFunction): Remote callable object. See ray.remote for more information.
            schedule (List[Any]): List of keys referring to RuntimeData values to be processed using the provided method.
            coreLogic (Optional[Callable]): Core logic of local function that will be forwarded to ray.

        Returns:
            Dict[ray.ObjectRef,int]: Dictionary containing the object references and their corresponding keys for keeping track of the progress and upholding the order of input data provided.
        """
        ## VERBOSE MODE
        
        # if coreLogic is provided, pass it to the wrapper
        if coreLogic is not None:
            return {worker.remote(coreLogic, self.RuntimeData_ref[schedule_index]):schedule_index
                    for schedule_index in tqdm(schedule, total=len(schedule), desc="Scheduling Workers", position = 0)}
        
        # if a ray compatible worker is provided, forward the worker directly
        return {worker.remote(self.RuntimeData_ref[schedule_index]):schedule_index
                for schedule_index in tqdm(schedule, total=len(schedule), desc="Scheduling Workers", position = 0)}
    
    def __silent_scheduler__(self, 
                             worker:ray.remote_function.RemoteFunction,
                             schedule:List,
                             coreLogic:Optional[Callable])->Dict[ray.ObjectRef,int]:
        """Silent scheduler that handles remote task execution.

        Args:
            worker (ray.remote_function.RemoteFunction): Remote callable object. See ray.remote for more information.
            schedule (List[Any]): List of keys referring to RuntimeData values to be processed using the provided method.
            coreLogic (Optional[Callable]): Core logic of local function that will be forwarded to ray.

        Returns:
            Dict[ray.ObjectRef,int]: Dictionary containing the object references and their corresponding keys for keeping track of the progress and upholding the order of input data provided.
        """
        ## SILENT MODE
        
        # if coreLogic is provided, pass it to the wrapper
        if coreLogic is not None:
            return {worker.remote(coreLogic, self.RuntimeData_ref[schedule_index]):schedule_index
                    for schedule_index in schedule}
        
        # if a ray compatible worker is provided, forward the worker directly
        return {worker.remote(self.RuntimeData_ref[schedule_index]):schedule_index
                for schedule_index in schedule}
        
    def __multicore_workflow__(self,
                               worker:Union[Callable, ray.remote_function.RemoteFunction],
                               schedule:List[Any],
                               listener:Callable,
                               scheduler:Callable,
                               coreLogic:Optional[Callable]
                               )->Tuple[bool, Dict[int,Any]]:
        """Workflow for the MultiCoreExecutionTool class. Handles the main execution logic.

        Args:
            worker (Union[Callable, ray.remote_function.RemoteFunction]): Remote callable object. See ray.remote for more information.
            schedule (List[Any]): List of keys referring to RuntimeData values to be processed using the provided method.
            listener (Callable): Chosen listener.
            scheduler (Callable): Chosen scheduler.
            coreLogic (Optional[Callable]): Core logic of local function that will be forwarded to ray.

        Returns:
            Tuple[bool, Dict[int,Any]]: Boolean flag signaling the success or the execution, Dictionary containing the results of the execution.
        """
        ## workflow and listening
        permission, finished_states = listener(scheduler(worker, schedule, coreLogic))
                
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
        """Silently listenes to the ray progress and retrieves the results.

        Args:
            object_references (Dict[ray.ObjectRef,int]): Dictionary containing the object references and their corresponding keys for keeping track of the progress and upholding the order of input data provided.

        Returns:
            Tuple[bool, Dict[int,Any]]: Boolean flag signaling the success or the execution, Dictionary containing the results of the execution.
        """
           
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
                
                if self.ListenerSleeptime > 0:
                    time.sleep(self.ListenerSleeptime)
            
            # sort and return the results
            finished_states = {object_references[ref]:ray.get(ref) for ref in finished_states}
            
            return True, finished_states
        
        except Exception as e:
            print(f'Error: {e}')
            return False, None

    def __verbose_listener__(self, object_references:Dict[ray.ObjectRef,int])->Tuple[bool, Dict[int,Any]]:
        """Listenes to and reports on the ray progress and system CPU and Memory. Retrieves results of successful tasks.

        Args:
            object_references (Dict[ray.ObjectRef,int]): Dictionary containing the object references and their corresponding keys for keeping track of the progress and upholding the order of input data provided.

        Returns:
            Tuple[bool, Dict[int,Any]]: Boolean flag signaling the success or the execution, Dictionary containing the results of the execution.
        """
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
                    if self.ListenerSleeptime > 0:
                        time.sleep(self.ListenerSleeptime)
                    
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
        """Run API for the MultiCoreExecutionTool class. Main API for running the provided worker on the provided data.

        Args:
            worker (Union[Callable, ray.remote_function.RemoteFunction]): Main worker or logic. Can be either ray.remote or a callable.

        Returns:
            bool: Boolean flag that is True if the execution was successful.
        """
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
    def initialize(self)->NoReturn:
        """Initialize the Ray cluster using the parameters found in sel.RuntimeMetadata['instance_metadata']".
           See https://docs.ray.io/en/latest/ray-core/api/doc/ray.init.html for more information.

        Returns:
            NoReturn: No Return.
        """        
        try:
            assert self.__initialize_ray_cluster__()
        except Exception as e:
            print(f'Error: {e}')
            return None
    def shutdown(self)->NoReturn:
        """Shutdown the Ray cluster.

        Returns:
            NoReturn: No Return.
        """
        self.__shutdown__()
    def reset(self)->NoReturn:
        """Resets RuntimeData and RuntimeData reference. Restores RuntimeMetadata defaults.

        Returns:
            NoReturn: No Return.
        """
        self.__reset__()
    def reboot(self)->NoReturn:
        """Reboot the MultiCoreExecutionTool object. Can be provided with new instance parameters. See instance attributes for more information.

        Returns:
            NoReturn: No Return.
        """
        self.__reboot__()
    def launch_dashboard(self)->bool:
        """Launch ray dashboard in default browser.

        Returns:
            bool: Status of the operation.
        """
        return self.__launch_dashboard__()

#%% Runtime Data Control
    def update_data(self, RuntimeData:Dict[Any,Dict[Any,Any]])->NoReturn:
        """Update the RuntimeData with the provided data.

        Args:
            RuntimeData (Dict[Any,Dict[Any,Any]]): Structured data to be processed by the methods.

        Returns:
            NoReturn: No Return.
        """
        self.__update_data__(RuntimeData)
        
    def update_metadata(self, **kwargs)->NoReturn:
        self.RuntimeMetadata.update(kwargs)

#%% Runtime Handling Backend
    def __initialize_metadata__(self,**kwargs)->NoReturn:
        """Initializes the metadata for the MultiCoreExecutionTool class. Contains default values and will overwrite with given values.

        Returns:
            NoReturn: No Return
        """
        ## Default Metadata
        self.RuntimeMetadata = {'instance_metadata':{'num_cpus': 1,
                                                     'num_gpus': 0,
                                                     'address': None,
                                                     'ignore_reinit_error': True},
                                 'task_metadata': {'num_cpus': 1,
                                                   'num_gpus': 0,
                                                   'num_returns': None},
                                 }
        # update metadata with given values
        self.RuntimeMetadata.update(kwargs)

    
    def __offload_on_init__(self, RuntimeData:Dict[Any,Dict[Any,Any]])->NoReturn:
        """Offload RuntimeData items to ray cluster on initialization if RuntimeData is provided.

        Args:
            RuntimeData (Dict[Any,Dict[Any,Any]]): Structured data to be processed by the methods.

        Returns:
            NoReturn: No Return
        """
        ## This has to be called AFTER the ray is initialized
        # otherwise, a new ray object will be created and the object references will be unreachable from within the main ray object.
        
        if RuntimeData is None:
            print('No Runtime Data provided. Use the "update()" method to update the Runtime Data prior to running methods.')
            return None
        
        ## Set RuntimeData
        self.RuntimeData = RuntimeData if RuntimeData is not None else None
        self.RuntimeData_ref = self.__offload_data__() if RuntimeData is not None else None
        
    def __initialize_ray_cluster__(self)->bool:
        """Initialize the Ray cluster using the parameters found in sel.RuntimeMetadata['instance_metadata']".
           See https://docs.ray.io/en/latest/ray-core/api/doc/ray.init.html for more information.
           
        Returns:
            NoReturn: No Return
        """
    
        if self.is_initalized():
            print('Ray is already initialized. Use "reboot()" to reboot the object.')
            return False
    
        if self.DEBUG:
            print('Setting up Ray...')
        
        # shutdown any stray ray instances
        ray.shutdown()
        
        # ray init
        cluster_context = ray.init(**self.RuntimeMetadata['instance_metadata'])
        self.DashboardURL = f"http://{cluster_context.dashboard_url}/"

        # dashboard
        if self.AutoLaunchDashboard:
            self.__launch_dashboard__()
        
        if self.DEBUG:
            print('Ray setup complete...')
            print(f'Ray Dashboard: {self.DashboardURL}')
        
        # set the runtime context
        self.runimte_context = cluster_context
        
        return True
    
    def __shutdown__(self)->bool:
        """Shutdown the Ray cluster.

        Returns:
            bool: True if the shutdown was successful.
        """
        if self.DEBUG:
            print('Shutting down Ray...')
        try:
            ray.shutdown()
            return True
        except Exception as e:
            print(f'Error: {e}')
            return False
        
    def __reset__(self)->NoReturn:
        """Resets RuntimeData and RuntimeData reference. Restores RuntimeMetadata defaults.
        
        Returns:
            NoReturn: No Return
        """
        self.RuntimeData_ref = None
        self.RuntimeData = None
        self.__initialize_metadata__()
         
    def __reboot__(self, **kwargs)->NoReturn:
        """Reboots the MultiCoreExecutionTool object. Can be provided with new instance parameters. See https://docs.ray.io/en/latest/ray-core/api/doc/ray.init.html for more information.

        Returns:
            NoReturn: _description_
        """
        InitInstructions = self.RuntimeMetadata['instance_metadata'] | kwargs
        try:
            self.__shutdown__()
            self.__initialize_ray_cluster__(**InitInstructions)
            self.__offload_data__()
        except Exception as e:
            print(f'Error: {e}')
            
    def __launch_dashboard__(self)->bool:
        """Launch ray dashboard in default browser.

        Returns:
            bool: Status of the operation.
        """
        if self.DEBUG:
            print('Preparing to launch ray dashboard...')
        
        if not self.is_initalized():
            print('Ray is not initialized. Use "initialize()" to initialize Ray.')
            return False
    
        try:
            webbrowser.get('windows-default').open(self.DashboardURL,
                                                    autoraise = True,
                                                    new = 2)
            return True
        except Exception as e:
            print(f'Error: {e}')
            return False

#%% Runtime Data Handling
    def __setup_schedule__(self)->List[Any]:
        """Bundle the RuntimeData keys into a list for scheduling.

        Returns:
            List[Any]: List of keys referring to RuntimeData values to be processed using the provided method.
        """

        self.RuntimeResults = {k:{'result':None, 'status':'pending'} for k in self.RuntimeData.keys()}
        return [k for k,v in self.RuntimeResults.items() if v['status'] == 'pending']

    def __update_data__(self, RuntimeData:Dict[Any,Dict[Any,Any]])->NoReturn:
        """Update the RuntimeData with the provided data and offload the data to the ray cluster.

        Args:
            RuntimeData (Dict[int,Dict[str,Any]]): Structured data to be processed by the methods.

        Returns:
            NoReturn: No Return
        """
        self.RuntimeData = RuntimeData
        self.RuntimeData_ref = self.__offload_data__()
        self.__setup_schedule__()
        
    def __offload_data__(self)->Dict[int,ray.ObjectRef]:
        """Offload the RuntimeData to the ray cluster.

        Returns:
            Dict[int,ray.ObjectRef]: Dictionary of keys and ray object references.
        """
        if self.DEBUG:
            print('Offloading data to Ray...')
        return {k:ray.put(v) for k,v in self.RuntimeData.items()}

#%% Helper
    def is_ray_compatible(self, func:Callable)->bool:
        """Check if the provided function is ray compatible.

        Args:
            func (Callable): Provided function.

        Returns:
            bool: True if the function is ray compatible. False otherwise.
        """
        if isinstance(func, ray.remote_function.RemoteFunction):
            return True
        return False 
    
    def is_initalized(self)->bool:
        """Check of the Ray cluster is initialized.

        Returns:
            bool: True if the Ray cluster is initialized. False otherwise.
        """
        if self.DEBUG:
            print('Checking Ray Status...')
        return ray.is_initialized()
    
    def get_results(self)->Dict[Any,Dict[str,Any]]:
        """Returns RuntimeResults.

        Returns:
            Dict[Any,Dict[Any,Any]]: Structured data containing the results of the execution.
        """
        if self.DEBUG:
            print('Fetching Results...')
        
        if self.RuntimeResults is None:
            print('No results found. Use the "run()" method to get results.')
            return None
        return self.RuntimeResults
