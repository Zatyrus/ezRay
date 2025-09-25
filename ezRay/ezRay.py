## Dependencies:
import json
import webbrowser
import datetime
from copy import deepcopy
from typing import Any, Callable, Dict, List, NoReturn, Optional, Tuple, Union

import psutil
import ray

# typing
import ray.remote_function
import ray.runtime_context

# context aware progress bar
# detect jupyter notebook
from IPython.core.getipython import get_ipython

try:
    ipy_str = str(type(get_ipython()))
    if "zmqshell" in ipy_str:
        pass
    else:
        pass
except Exception as _:
    pass

## loal
from .scheduler import Scheduler
from .listener import Listener


# %% Multi Core Execution Main
class MultiCoreExecutionTool:
    RuntimeData: Dict[Any, Dict[Any, Any]]

    RuntimeResults: Dict[Any, Dict[str, Any]]
    RuntimeContext: ray.runtime_context.RuntimeContext
    RuntimeMetadata: Dict[str, Union[str, bool, int, float]]
    RuntimeArchive: Dict[str, Dict[Any, Dict[str, Any]]]
    DashboardURL: str

    AutoLaunchDashboard: bool
    silent: bool
    DEBUG: bool

    SingleShot: bool
    AutoContinue: bool
    AutoArchive: bool

    # %% Properties

    ## Runtime Data
    @property
    def RuntimeData(self) -> Dict[Any, Dict[Any, Any]]:
        return self._RuntimeData

    @RuntimeData.setter
    def RuntimeData(self, value: Dict[Any, Dict[Any, Any]]) -> NoReturn:
        self._RuntimeData = value

    @RuntimeData.deleter
    def RuntimeData(self) -> NoReturn:
        del self._RuntimeData

    ## Runtime Results
    @property
    def RuntimeResults(self) -> Dict[Any, Dict[str, Any]]:
        return self._RuntimeResults

    @RuntimeResults.setter
    def RuntimeResults(self, value: Dict[Any, Dict[str, Any]]) -> NoReturn:
        raise ValueError(
            "RuntimeResults is read-only. Use update_data() to reset the results."
        )

    @RuntimeResults.deleter
    def RuntimeResults(self) -> NoReturn:
        del self._RuntimeResults

    ## Runtime Context
    @property
    def RuntimeContext(self) -> ray.runtime_context.RuntimeContext:
        return self._RuntimeContext

    @RuntimeContext.setter
    def RuntimeContext(self, value: ray.runtime_context.RuntimeContext) -> NoReturn:
        self._RuntimeContext = value

    @RuntimeContext.deleter
    def RuntimeContext(self) -> NoReturn:
        del self._RuntimeContext

    ## Runtime Metadata
    @property
    def RuntimeMetadata(self) -> Dict[str, Union[str, bool, int, float]]:
        return self._RuntimeMetadata

    @RuntimeMetadata.setter
    def RuntimeMetadata(
        self, value: Dict[str, Union[str, bool, int, float]]
    ) -> NoReturn:
        self._RuntimeMetadata = value

    @RuntimeMetadata.deleter
    def RuntimeMetadata(self) -> NoReturn:
        del self._RuntimeMetadata

    ## Runtime Node Metadata
    @property
    def NodeMetadata(self) -> Dict[str, Any]:
        return self._NodeMetadata

    @NodeMetadata.setter
    def NodeMetadata(self, value: Dict[str, Any]) -> NoReturn:
        self._NodeMetadata = value
        self.__update_RuntimeMetadata__(NodeMetadata=value)

    @NodeMetadata.deleter
    def NodeMetadata(self) -> NoReturn:
        del self._NodeMetadata

    ## Runtime Archive
    @property
    def RuntimeArchive(self) -> Dict[str, Dict[Any, Dict[str, Any]]]:
        return self._RuntimeArchive

    @RuntimeArchive.setter
    def RuntimeArchive(self, value: Dict[str, Dict[Any, Dict[str, Any]]]) -> NoReturn:
        self._RuntimeArchive = value

    @RuntimeArchive.deleter
    def RuntimeArchive(self) -> NoReturn:
        del self._RuntimeArchive

    ## Dashboard URL
    @property
    def DashboardURL(self) -> str:
        return self._DashboardURL

    @DashboardURL.setter
    def DashboardURL(self, value: str) -> NoReturn:
        self._DashboardURL = value
        self.__update_RuntimeMetadata__(DashboardURL=value)

    @DashboardURL.deleter
    def DashboardURL(self) -> NoReturn:
        del self._DashboardURL

    ## Auto Launch Dashboard
    @property
    def AutoLaunchDashboard(self) -> bool:
        return self._AutoLaunchDashboard

    @AutoLaunchDashboard.setter
    def AutoLaunchDashboard(self, value: bool) -> NoReturn:
        self._AutoLaunchDashboard = value
        self.__update_RuntimeMetadata__(AutoLaunchDashboard=value)

    @AutoLaunchDashboard.deleter
    def AutoLaunchDashboard(self) -> NoReturn:
        del self._AutoLaunchDashboard

    ## Silent
    @property
    def silent(self) -> bool:
        return self._silent

    @silent.setter
    def silent(self, value: bool) -> NoReturn:
        self._silent = value
        self.__update_RuntimeMetadata__(silent=value)

    @silent.deleter
    def silent(self) -> NoReturn:
        del self._silent

    ## Debug
    @property
    def DEBUG(self) -> bool:
        return self._DEBUG

    @DEBUG.setter
    def DEBUG(self, value: bool) -> NoReturn:
        self._DEBUG = value
        self.__update_RuntimeMetadata__(DEBUG=value)

    @DEBUG.deleter
    def DEBUG(self) -> NoReturn:
        del self._DEBUG

    ## SingleShot
    @property
    def SingleShot(self) -> bool:
        return self._SingleShot

    @SingleShot.setter
    def SingleShot(self, value: bool) -> NoReturn:
        self._SingleShot = value
        self.__update_RuntimeMetadata__(SingleShot=value)

        # handle dependent attributes
        if value:
            self._AutoArchive = False
            self._AutoContinue = True
            self.__update_RuntimeMetadata__(AutoArchive=False, AutoContinue=True)
            print("SingleShot mode is enabled. Archive disabled. AutoContinue enabled.")
        elif not value:
            self._AutoArchive = True
            self._AutoContinue = False
            self.__update_RuntimeMetadata__(AutoArchive=True, AutoContinue=False)
            print(
                "SingleShot mode is disabled. Archive enabled. AutoContinue disabled."
            )
        else:
            pass

    @SingleShot.deleter
    def SingleShot(self) -> NoReturn:
        del self._SingleShot

    ## AutoContinue
    @property
    def AutoContinue(self) -> bool:
        return self._AutoContinue

    @AutoContinue.setter
    def AutoContinue(self, value: bool) -> NoReturn:
        self._AutoContinue = value
        self.__update_RuntimeMetadata__(AutoContinue=value)

    @AutoContinue.deleter
    def AutoContinue(self) -> NoReturn:
        del self._AutoContinue

    ## AutoArchive
    @property
    def AutoArchive(self) -> bool:
        return self._AutoArchive

    @AutoArchive.setter
    def AutoArchive(self, value: bool) -> NoReturn:
        self._AutoArchive = value
        self.__update_RuntimeMetadata__(AutoArchive=value)

    @AutoArchive.deleter
    def AutoArchive(self) -> NoReturn:
        del self._AutoArchive

    def __init__(
        self, RuntimeData: Dict[Any, Dict[Any, Any]] = {}, /, **kwargs
    ) -> NoReturn:
        """Constructor for the MultiCoreExecutionTool class.

        Args:
            RuntimeData (Dict[Any,Dict[Any,Any]], optional): Dictionary containing keyword arguments for the methods to run. Defaults to None.

        Returns:
            MultiCoreExecutionTool: MultiCoreExecutionTool object.
        """
        ## Default Verbosity
        self._AutoLaunchDashboard = False
        self._silent = False
        self._DEBUG = False

        ## Initialize attributes
        self._DashboardURL = None
        self._RuntimeContext = None
        self._RuntimeMetadata = {}
        self._RuntimeResults = {}
        self._RuntimeArchive = {}

        ## Set Behavior
        self._SingleShot = False
        self._AutoContinue = False
        self._AutoArchive = True

        ## Setattributes
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        ## set the debug flag
        if "DEBUG" in kwargs.keys():
            self._DEBUG = kwargs["DEBUG"]
            if self._DEBUG:
                print("Debug mode is enabled. Using verbose mode.")
                self._silent = False

        if "SingleShot" in kwargs.keys():
            self._SingleShot = kwargs["SingleShot"]

            if self._SingleShot:
                self._AutoArchive = False
                self._AutoContinue = True
                print(
                    "SingleShot mode is enabled. Archive disabled. AutoContinue enabled."
                )

        self.__post_init__(RuntimeData, **kwargs)

    def __post_init__(
        self, RuntimeData: Dict[Any, Dict[Any, Any]], /, **kwargs
    ) -> NoReturn:
        """Post initialization method for the MultiCoreExecutionTool class. Handles routine initialization tasks.

        Args:
            RuntimeData (Dict[Any,Dict[Any,Any]]): Structured data to be processed by the methods.

        Returns:
            NoReturn: No Return
        """
        self.__initialize_metadata__(**kwargs)
        self.__initialize_ray_cluster__()
        self.__offload_on_init__(RuntimeData)

    # %% Class methods
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MultiCoreExecutionTool":
        """Convenience method to create a MultiCoreExecutionTool object from a dictionary.

        Returns:
            MultiCoreExecutionTool: MultiCoreExecutionTool object.
        """
        return cls(**data)

    @classmethod
    def from_json(cls, path: str) -> "MultiCoreExecutionTool":
        """Convenience method to create a MultiCoreExecutionTool object from a JSON file.

        Args:
            path (str): Path to the JSON file.

        Returns:
            MultiCoreExecutionTool: MultiCoreExecutionTool object.
        """
        with open(path, "r") as file:
            data = json.load(file)
        return cls(**data)

    # %% Ray Wrapper
    def __setup_wrapper__(self) -> Callable:
        @ray.remote(**self._RuntimeMetadata["task_metadata"])
        def __method_wrapper__(
            method: Callable, input: Dict[Any, Any]
        ) -> ray.remote_function.RemoteFunction:
            """Ray wrapper for arbitrary function logic.

            Args:
                method (Callable): Arbitrary method that takes at least one input.
                input (Dict[Any,Any]): Method input that will be forwarded to the main logic.

            Returns:
                Callable: Returns a ray.remote callable object.
            """
            return method(**input)

        return __method_wrapper__

    # %% Main Backend
    def __run__(
        self, worker: Union[Callable, ray.remote_function.RemoteFunction]
    ) -> bool:
        """Main execution method for the MultiCoreExecutionTool class. Runs the provided worker on the provided data.

        Args:
            worker (Union[Callable, ray.remote_function.RemoteFunction]): Main worker or logic. Can be either ray.remote or a callable.

        Raises:
            Exception: Exception is raised if the core logic is not ray compatible.

        Returns:
            bool: Boolean flag that is True if the execution is successful.
        """

        # forwards the worker to the batch method
        return self.__batch__(worker, runIDs="all")

    def __batch__(
        self,
        worker: Union[Callable, ray.remote_function.RemoteFunction],
        *,
        runIDs: Union[int, List[Any], str] = "all",
    ) -> bool:
        """Batch execution method for the MultiCoreExecutionTool class. Runs the provided worker on the provided data.

        Args:
            worker (Union[Callable, ray.remote_function.RemoteFunction]): Main worker or logic. Can be either ray.remote or a callable.
            runIDs (Union[int, List[Any], str], optional): RunIDs to process. Defaults to 'all'.

        Raises:
            Exception: Exception is raised if the core logic is not ray compatible.

        Returns:
            bool: Boolean flag that is True if the execution
        """

        ## check if ray is initialized
        if not ray.is_initialized():
            raise Exception(
                "Ray is not initialized. Use object.initialize() to initialize Ray."
            )

        if not self.__is_ray_compatible__(worker):
            try:
                coreLogic = worker
                worker = self.__setup_wrapper__()
            except Exception as e:
                print(f"Error: {e}")
                return False

        ## prepare schedule
        schedule = self.__setup_schedule__()

        ## check for pending tasks
        if not self.__has_pending_results__():
            print("No pending tasks found. Exiting...")
            return True

        ## handle runIDs, skip if all
        if not runIDs == "all":
            ## check for runIDs
            if not self.__RunIDs_in_RuntimeData__(runIDs):
                print(
                    "Invalid RunIDs. Please provide a list of keys referring to the RuntimeData or a number of tasks to run that is <= the total amount of tasks."
                )
                return False

            ## select the runIDs
            if isinstance(runIDs, int):
                schedule = schedule[:runIDs]
            elif isinstance(runIDs, list):
                schedule = [k for k in schedule if k in runIDs]
            else:
                print(
                    "Invalid RunIDs. Please provide a list of keys referring to the RuntimeData or a number of tasks to run that is <= the total amount of tasks."
                )
                return False

            if self._DEBUG:
                print(f"Running {runIDs} tasks...")

        ## check for schedule
        if len(schedule) == 0:
            print("No pending tasks to run. Exiting...")
            return True

        ## workflow factory
        if self._silent:
            permision, states = self.__multicore_workflow__(
                worker=worker,
                schedule=schedule,
                listener=Listener(DEBUG=self._DEBUG).silent,
                scheduler=Scheduler(DEBUG=self._DEBUG).silent,
                coreLogic=coreLogic if "coreLogic" in locals() else None,
            )
        else:
            permision, states = self.__multicore_workflow__(
                worker=worker,
                schedule=schedule,
                listener=Listener(DEBUG=self._DEBUG).verbose,
                scheduler=Scheduler(DEBUG=self._DEBUG).verbose,
                coreLogic=coreLogic if "coreLogic" in locals() else None,
            )

        ## update the results
        if permision:
            if self._DEBUG:
                print("Writing result refs to RuntimeResults...")
            for k in schedule:
                self._RuntimeResults[k].update(
                    {"result": states[k], "status": "completed"}
                )

        return permision

    def __multicore_workflow__(
        self,
        worker: Union[Callable, ray.remote_function.RemoteFunction],
        schedule: List[Any],
        listener: Callable,
        scheduler: Callable,
        coreLogic: Optional[Callable],
    ) -> Tuple[bool, Dict[int, Any]]:
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
        permission, finished_states = listener(
            scheduler(worker, self.RuntimeData_ref, schedule, coreLogic)
        )

        ## check completion
        if permission:
            self._RuntimeResults | {
                k: {"result": v, "status": "completed"}
                for k, v in finished_states.items()
            }

            ## Shutdown Ray
            if self._DEBUG:
                print("Multi Core Execution Complete...")
                print("Use 'shutdown_multi_core()' to shutdown the cluster.")

            return True, finished_states

        return False, None

    ##### API #####
    # %% Main Execution
    def run(
        self, worker: Union[Callable, ray.remote_function.RemoteFunction]
    ) -> Union[bool, Dict[Any, Dict[str, Any]]]:
        """Run API for the MultiCoreExecutionTool class. Main API for running the provided worker on the provided data.

        Args:
            worker (Union[Callable, ray.remote_function.RemoteFunction]): Main worker or logic. Can be either ray.remote or a callable.

        Returns:
            bool: Boolean flag that is True if the execution was successful.
        """
        try:
            permission: bool = self.__run__(worker)
            assert permission

            if self._DEBUG:
                print("Multi Core Execution Complete...")
                print('Use "get_results()" to get the results.')

        except Exception as e:
            print(f"Error: {e}")
            return False

        if self._SingleShot or self._AutoContinue:
            return self.next()
        return True

    def batch(
        self,
        worker: Union[Callable, ray.remote_function.RemoteFunction],
        *,
        runIDs: Union[int, List[Any], str] = "all",
    ) -> Union[bool, Dict[Any, Dict[str, Any]]]:
        """Batch API for the MultiCoreExecutionTool class. Main API for running the provided worker on the provided data.

        Args:
            worker (Union[Callable, ray.remote_function.RemoteFunction]): Main worker or logic. Can be either ray.remote or a callable.
            runIDs (Union[int, List[Any], str], optional): RunIDs to process. Defaults to 'all'.

        Returns:
            bool: Boolean flag that is True if the execution was successful.
        """
        try:
            permission: bool = self.__batch__(worker, runIDs=runIDs)
            assert permission

            if self._DEBUG:
                print("Multi Core Execution Complete...")
                print('Use "get_results()" to get the results.')

        except Exception as e:
            print(f"Error: {e}")
            return False

        if self._SingleShot or self._AutoContinue:
            return self.next()
        return True

    # %% Runtime Control
    def initialize(self) -> NoReturn:
        """Initialize the Ray cluster using the parameters found in sel.RuntimeMetadata['instance_metadata']".
           See https://docs.ray.io/en/latest/ray-core/api/doc/ray.init.html for more information.

        Returns:
            NoReturn: No Return.
        """
        try:
            assert self.__initialize_ray_cluster__()
        except Exception as e:
            print(f"Error: {e}")
            return None

    def shutdown(self) -> NoReturn:
        """Shutdown the Ray cluster.

        Returns:
            NoReturn: No Return.
        """
        self.__shutdown__()

    def reset(self) -> NoReturn:
        """Resets RuntimeData and RuntimeData reference. Restores RuntimeMetadata defaults.

        Returns:
            NoReturn: No Return.
        """
        self.__reset__()

    def reboot(self) -> NoReturn:
        """Reboot the MultiCoreExecutionTool object. Can be provided with new instance parameters. See instance attributes for more information.

        Returns:
            NoReturn: No Return.
        """
        self.__reboot__()

    def launch_dashboard(self) -> bool:
        """Launch ray dashboard in default browser.

        Returns:
            bool: Status of the operation.
        """
        return self.__launch_dashboard__()

    # %% Runtime Data Control
    def update_data(self, RuntimeData: Dict[Any, Dict[Any, Any]]) -> NoReturn:
        """Update the RuntimeData with the provided data.

        Args:
            RuntimeData (Dict[Any,Dict[Any,Any]]): Structured data to be processed by the methods.

        Returns:
            NoReturn: No Return.
        """
        self.__update_data__(RuntimeData)

    def update_metadata(self, **kwargs) -> NoReturn:
        self._RuntimeMetadata.update(kwargs)

        ## check if the metadata is valid
        ## we will only notify the user if the metadata is invalid or the DEBUG flag is set
        status = self.__ressource_requirements_met__()
        if not status:
            print("Please adjust the metadata.")
        elif status and self._DEBUG:
            print("Metadata updated.")

    # %% Runtime Handling Backend
    def __initialize_metadata__(self, **kwargs) -> NoReturn:
        """Initializes the metadata for the MultiCoreExecutionTool class. Contains default values and will overwrite with given values.

        Returns:
            NoReturn: No Return
        """
        ## Default Metadata
        self._RuntimeMetadata = {
            "instance_metadata": {
                "num_cpus": 1,
                "num_gpus": 0,
                "address": None,
                "ignore_reinit_error": True,
            },
            "task_metadata": {"num_cpus": 1, "num_gpus": 0, "num_returns": None},
        }
        # update metadata with given values
        self._RuntimeMetadata.update(kwargs)

        ## check if the metadata is valid
        ## we will only notify the user if the metadata is invalid or the DEBUG flag is set
        status = self.__ressource_requirements_met__()
        if not status:
            print("Please adjust the metadata.")
        elif status and self._DEBUG:
            print("Metadata updated.")

    def __offload_on_init__(self, RuntimeData: Dict[Any, Dict[Any, Any]]) -> NoReturn:
        """Offload RuntimeData items to ray cluster on initialization if RuntimeData is provided.

        Args:
            RuntimeData (Dict[Any,Dict[Any,Any]]): Structured data to be processed by the methods.

        Returns:
            NoReturn: No Return
        """
        ## This has to be called AFTER the ray is initialized
        # otherwise, a new ray object will be created and the object references will be unreachable from within the main ray object.

        if RuntimeData is None:
            print(
                'No Runtime Data provided. Use the "update_data()" method to update the Runtime Data prior to running methods.'
            )
            return None

        ## Set RuntimeData
        self.RuntimeData = RuntimeData if RuntimeData is not None else None
        self.RuntimeData_ref = (
            self.__offload_data__() if RuntimeData is not None else None
        )
        self._RuntimeResults = (
            self.__setup_RuntimeResults__() if RuntimeData is not None else None
        )
        self._RuntimeArchive = {} if RuntimeData is not None else None

    def __initialize_ray_cluster__(self) -> bool:
        """Initialize the Ray cluster using the parameters found in sel.RuntimeMetadata['instance_metadata']".
           See https://docs.ray.io/en/latest/ray-core/api/doc/ray.init.html for more information.

        Returns:
            NoReturn: No Return
        """

        if self.__is_initalized__():
            print('Ray is already initialized. Use "reboot()" to reboot the object.')
            return False

        if self._DEBUG:
            print("Setting up Ray...")

        # shutdown any stray ray instances
        ray.shutdown()

        # ray init
        RuntimeContext = ray.init(**self._RuntimeMetadata["instance_metadata"])
        self._DashboardURL = f"http://{RuntimeContext.dashboard_url}/"
        self._NodeMetadata = RuntimeContext.address_info
        self.__update_RuntimeMetadata__(
            NodeMetadata=RuntimeContext.address_info, DashboardURL=self._DashboardURL
        )

        # dashboard
        if self._AutoLaunchDashboard:
            self.__launch_dashboard__()

        if self._DEBUG:
            print("Ray setup complete...")
            print(f"Ray Dashboard: {self._DashboardURL}")

        # set the runtime context
        self._RuntimeContext = RuntimeContext

        return True

    def __shutdown__(self) -> bool:
        """Shutdown the Ray cluster.

        Returns:
            bool: True if the shutdown was successful.
        """
        if self._DEBUG:
            print("Shutting down Ray...")
        try:
            ray.shutdown()
            return True
        except Exception as e:
            print(f"Error: {e}")
            return False

    def __reset__(self) -> NoReturn:
        """Resets RuntimeData and RuntimeData reference. Restores RuntimeMetadata defaults.

        Returns:
            NoReturn: No Return
        """
        self.RuntimeData_ref = None
        self.RuntimeData = None
        self.__initialize_metadata__()

    def __reboot__(self) -> NoReturn:
        """Reboots the MultiCoreExecutionTool object. Can be provided with new instance parameters. See https://docs.ray.io/en/latest/ray-core/api/doc/ray.init.html for more information.

        Returns:
            NoReturn: _description_
        """
        try:
            self.__shutdown__()
            self.__initialize_ray_cluster__()
            self.__offload_data__()
        except Exception as e:
            print(f"Error: {e}")

    def __launch_dashboard__(self) -> bool:
        """Launch ray dashboard in default browser.

        Returns:
            bool: Status of the operation.
        """
        if self._DEBUG:
            print("Preparing to launch ray dashboard...")

        if not self.__is_initalized__():
            print('Ray is not initialized. Use "initialize()" to initialize Ray.')
            return False

        try:
            webbrowser.get("windows-default").open(
                self._DashboardURL, autoraise=True, new=2
            )
            return True
        except Exception as e:
            print(f"Error: {e}")
            return False

    # %% Runtime Data Handling
    def __setup_schedule__(self) -> List[Any]:
        """Bundle the RuntimeData keys into a list for scheduling.

        Returns:
            List[Any]: List of keys referring to RuntimeData values to be processed using the provided method.
        """
        return [k for k, v in self._RuntimeResults.items() if v["status"] == "pending"]

    def __setup_RuntimeResults__(self) -> Dict[int, Dict[str, Any]]:
        """Setup the RuntimeResults dictionary.

        Returns:
            Dict[int,Dict[str,Any]]: Dictionary containing the results of the execution
        """
        return {
            k: {"result": None, "status": "pending"} for k in self.RuntimeData.keys()
        }

    def __offload_data__(self) -> Dict[int, ray.ObjectRef]:
        """Offload the RuntimeData to the ray cluster.

        Returns:
            Dict[int,ray.ObjectRef]: Dictionary of keys and ray object references.
        """
        if self._DEBUG:
            print("Offloading data to Ray...")
        return {k: ray.put(v) for k, v in self.RuntimeData.items()}

    def __move_results_to_archive__(self) -> NoReturn:
        """Move the RuntimeResults to the RuntimeArchive.

        Returns:
            NoReturn: No Return
        """
        if self._DEBUG:
            print("Moving results to RuntimeArchive...")

        # set status to archived
        for k, v in self._RuntimeResults.items():
            if v["status"] == "completed":
                v["status"] = "archived"
            if v["status"] == "retrieved":
                v["status"] = "archived"
            if v["status"] == "pending":
                v["status"] = "no result"

        # write to archive
        self._RuntimeArchive[datetime.datetime.now().isoformat(timespec="seconds")] = (
            deepcopy(self._RuntimeResults)
        )
        # reset results
        self._RuntimeResults = self.__setup_RuntimeResults__()

    def __update_data__(self, RuntimeData: Dict[Any, Dict[Any, Any]]) -> NoReturn:
        """Update the RuntimeData with the provided data and offload the data to the ray cluster.

        Args:
            RuntimeData (Dict[int,Dict[str,Any]]): Structured data to be processed by the methods.

        Returns:
            NoReturn: No Return
        """
        if self._DEBUG:
            print("Updating Runtime Data...")

        self.RuntimeData = RuntimeData
        self.RuntimeData_ref = self.__offload_data__()

        if (
            self._RuntimeResults is not None
            and self._AutoArchive
            and not self.__all_results_pending__()
        ):
            self.__move_results_to_archive__()
            print("Previous results detected and moved to RuntimArchive.")
        else:
            self._RuntimeResults = self.__setup_RuntimeResults__()

    # %% Helper
    def __update_RuntimeMetadata__(self, **kwargs) -> NoReturn:
        """Update the RuntimeMetadata with the provided keyword arguments.

        Args:
            **kwargs: Keyword arguments to update the RuntimeMetadata.

        Returns:
            NoReturn: No Return
        """
        self._RuntimeMetadata.update(kwargs)

    def __cpus_available__(self) -> bool:
        """Check if the Ray cluster has enough CPUs.

        Args:
            num_cpus (int): Number of CPUs.

        Returns:
            bool: True if the Ray cluster has enough CPUs. False otherwise.
        """
        if self._DEBUG:
            print("Checking CPU availability...")
        try:
            assert (
                psutil.cpu_count()
                >= self._RuntimeMetadata["instance_metadata"]["num_cpus"]
            )
            return True
        except AssertionError:
            print("Error: Not enough CPUs available.")
            print(
                "Requested CPUs: ",
                self._RuntimeMetadata["instance_metadata"]["num_cpus"],
            )
            print("Available CPUs: ", psutil.cpu_count())
            return False

    def __tasks_meet_cpu_requirements__(self) -> bool:
        """Check if the tasks meet the CPU requirements.

        Args:
            num_cpus (int): Number of CPUs.

        Returns:
            bool: True if the tasks meet the CPU requirements. False otherwise.
        """
        if self._DEBUG:
            print("Checking CPU requirements...")
        try:
            assert (
                self._RuntimeMetadata["task_metadata"]["num_cpus"]
                <= self._RuntimeMetadata["instance_metadata"]["num_cpus"]
            )
            return True
        except AssertionError:
            print(
                "Error: Tasks are assigned too many CPUs. None will be able to execute on the Ray cluster."
            )
            print(
                "Requested CPUs per Task: ",
                self._RuntimeMetadata["task_metadata"]["num_cpus"],
            )
            print(
                "Available CPUs in Cluster: ",
                self._RuntimeMetadata["instance_metadata"]["num_cpus"],
            )
            print(
                "Please adjust the number of CPUs per task. Or increase the number of CPUs in the Ray cluster."
            )
            return False

    def __warn_gpu_is_used__(self) -> bool:
        """Check if the Ray cluster has enough GPUs.

        Args:
            num_gpus (int): Number of GPUs.

        Returns:
            bool: True if the Ray cluster has enough GPUs. False otherwise.
        """
        if self._DEBUG:
            print("Checking GPU ise used...")
        if self._RuntimeMetadata["instance_metadata"]["num_gpus"] > 0:
            print("Warning: GPU is used.")
            print("Please make sure that the Ray cluster has enough GPUs.")
            print("You may need to manually check the GPU availability.")
            print(
                "Alternatively, you can use torch.cuda.is_available() to check the GPU availability."
            )
        return True

    def __ressource_requirements_met__(self) -> bool:
        """Check if the ressource requirements are met.

        Args:
            num_cpus (int): Number of CPUs.
            num_gpus (int): Number of GPUs.

        Returns:
            bool: True if the ressource requirements are met. False otherwise.
        """
        if self._DEBUG:
            print("Checking ressource requirements...")
        return (
            self.__cpus_available__()
            and self.__warn_gpu_is_used__()
            and self.__tasks_meet_cpu_requirements__()
        )

    def __is_ray_compatible__(self, func: Callable) -> bool:
        """Check if the provided function is ray compatible.

        Args:
            func (Callable): Provided function.

        Returns:
            bool: True if the function is ray compatible. False otherwise.
        """
        if isinstance(func, ray.remote_function.RemoteFunction):
            return True
        return False

    def __is_initalized__(self) -> bool:
        """Check of the Ray cluster is initialized.

        Returns:
            bool: True if the Ray cluster is initialized. False otherwise.
        """
        if self._DEBUG:
            print("Checking Ray Status...")
        return ray.is_initialized()

    def __has_pending_results__(self) -> bool:
        """Check if there are pending results.

        Returns:
            bool: True if there are pending results. False otherwise.
        """
        if self._DEBUG:
            print("Checking for pending results...")
        return any([v["status"] == "pending" for k, v in self._RuntimeResults.items()])

    def __all_results_pending__(self) -> bool:
        """Check if all results are pending.

        Returns:
            bool: True if all results are pending. False otherwise.
        """
        if self._DEBUG:
            print("Checking if all results are pending...")
        return all([v["status"] == "pending" for k, v in self._RuntimeResults.items()])

    def __has_completed_results__(self) -> bool:
        """Check if there are completed results.

        Returns:
            bool: True if there are completed results. False otherwise.
        """
        if self._DEBUG:
            print("Checking for completed results...")
        return any(
            [v["status"] == "completed" for k, v in self._RuntimeResults.items()]
        )

    def __all_results_retrieved__(self) -> bool:
        """Check if all results are retrieved.

        Returns:
            bool: True if all results are retrieved. False otherwise.
        """
        if self._DEBUG:
            print("Checking if all results are retrieved...")
        return all(
            [v["status"] == "retrieved" for k, v in self._RuntimeResults.items()]
        )

    def __RunIDs_in_RuntimeData__(self, RunIDs: Union[int, List[Any]]) -> bool:
        """Check if the provided RunIDs are in the RuntimeData.

        Args:
            RunIDs (Union[int, List[Any]]): RunIDs to check.

        Returns:
            bool: True if the RunIDs are in the RuntimeData. False otherwise.
        """
        if self._DEBUG:
            print("Checking if RunIDs are in RuntimeData...")
        if isinstance(RunIDs, int):
            return RunIDs <= len(self.RuntimeData)
        return all([k in self.RuntimeData.keys() for k in RunIDs])

    def retreive_data(self) -> bool:
        """Retreive the RuntimeData.

        Returns:
            Dict[Any,Dict[Any,Any]]: Structured data to be processed by the methods.
        """
        if self._DEBUG:
            print("Retreiving Data...")

        if self._RuntimeResults is None:
            print('No results found. Use the "run()" method to get results.')
            return False

        try:
            for refKey, objRef in self._RuntimeResults.items():
                if objRef["status"] == "completed":
                    self._RuntimeResults[refKey].update(
                        {"result": ray.get(objRef["result"])}
                    )
                    self._RuntimeResults[refKey].update({"status": "retrieved"})
        except Exception as e:
            print(f"Error: {e}")
            return False

        return True

    def get_results(self) -> Dict[Any, Dict[str, Any]]:
        """Returns RuntimeResults.

        Returns:
            Dict[Any,Dict[Any,Any]]: Structured data containing the results of the execution.
        """
        if self._DEBUG:
            print("Fetching Results...")

        if self._RuntimeResults is None:
            print('No results found. Use the "run()" method to get results.')
            return None

        if self.__has_pending_results__():
            print('Pending results found. Use the "run()" method to get results.')

        if self.__all_results_retrieved__():
            return deepcopy(self._RuntimeResults)

        elif self.__has_completed_results__():
            self.retreive_data()
            return deepcopy(self._RuntimeResults)

        else:
            print('No results found. Use the "run()" method to get results.')
            return None

    def get_archive(self) -> Dict[str, Dict[Any, Dict[str, Any]]]:
        """Returns RuntimeArchive.

        Returns:
            Dict[str,Dict[Any,Dict[str,Any]]]: Structured data containing the archived results.
        """
        if self._DEBUG:
            print("Fetching Archive...")
        return deepcopy(self._RuntimeArchive)

    def get_archive_keys(self) -> List[str]:
        """Returns the keys of the RuntimeArchive.

        Returns:
            List[str]: List of keys referring to the RuntimeArchive values.
        """
        if self._DEBUG:
            print("Fetching Archive Keys...")
        return list(self._RuntimeArchive.keys())

    def get_all_results(
        self,
    ) -> Tuple[Dict[Any, Dict[str, Any]], Dict[str, Dict[Any, Dict[str, Any]]]]:
        """Returns RuntimeResults and RuntimeArchive.

        Returns:
            Tuple[Dict[Any,Dict[str,Any]],Dict[str,Dict[Any,Dict[str,Any]]]: Structured data containing the results of the execution and the archived results.
        """
        if self._DEBUG:
            print("Fetching All Results...")
        return self.get_results(), self.get_archive()

    def archive_results(self) -> bool:
        """Move the RuntimeResults to the RuntimeArchive.

        Returns:
            NoReturn: No Return.
        """
        if self._DEBUG:
            print("Archiving Results...")
        try:
            self.__move_results_to_archive__()
            return True
        except Exception as e:
            print(f"Error: {e}")
            return False

    def next(self) -> bool:
        if self._DEBUG:
            print("Moving to next task...")

        if self.__has_pending_results__():
            print(
                "Pending results found. Continuing to next task. Pending results will not be archived."
            )

        try:
            # handle SingleShot mode <- is exclusive from AutoArchive
            if self._SingleShot:
                current_results: Dict[str, Dict[Any, Any]] = deepcopy(
                    self.get_results()
                )
                self._RuntimeResults = self.__setup_RuntimeResults__()
                return current_results

            # handle AutoArchive mode
            if self._AutoArchive:
                self.__move_results_to_archive__()

            if (
                not self._AutoArchive and self._AutoContinue
            ):  # this is a case that should not happen; i put this here for safety
                if not self.__has_completed_results__():
                    print("No completed results found. Cannot continue to next task.")
                    return False
                print("Continuing to next task. Current results will not be archived.")
                print("The results of the current task are being overwritten.")

            # to go to next task, we need to reset the RuntimeResults
            # this will set all statuses to pending and delete the current results
            self._RuntimeResults = self.__setup_RuntimeResults__()

        except Exception as e:
            print(f"Error: {e}")
            return False
        return True
