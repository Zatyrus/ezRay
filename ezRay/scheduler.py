## Dependencies:
import json
import time
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
from IPython import get_ipython

try:
    ipy_str = str(type(get_ipython()))
    if "zmqshell" in ipy_str:
        from tqdm.notebook import tqdm
    else:
        from tqdm import tqdm
except Exception as _:
    from tqdm import tqdm
    
class Scheduler:
    """Scheduler class that handles the scheduling of remote tasks."""
    def __init__(self, DEBUG: bool = False)->NoReturn:
        """Initialize the Scheduler

        Args:
            DEBUG (bool, optional): Debug flag; Changes verbostiy. Defaults to False.
        """
        self.DEBUG = DEBUG
    
    def verbose(
        self,
        worker: ray.remote_function.RemoteFunction,
        data_ref: Dict[int, ray.ObjectRef],
        schedule: List[Any],
        coreLogic: Optional[Callable],
    ) -> Dict[ray.ObjectRef, int]:
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
            return {
                worker.remote(
                    coreLogic, data_ref[schedule_index]
                ): schedule_index
                for schedule_index in tqdm(
                    schedule, total=len(schedule), desc="Scheduling Workers", position=0
                )
            }

        # if a ray compatible worker is provided, forward the worker directly
        return {
            worker.remote(data_ref[schedule_index]): schedule_index
            for schedule_index in tqdm(
                schedule, total=len(schedule), desc="Scheduling Workers", position=0
            )
        }

    def silent(
        self,
        worker: ray.remote_function.RemoteFunction,
        data_ref: Dict[int, ray.ObjectRef],
        schedule: List,
        coreLogic: Optional[Callable],
    ) -> Dict[ray.ObjectRef, int]:
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
            return {
                worker.remote(
                    coreLogic, data_ref[schedule_index]
                ): schedule_index
                for schedule_index in schedule
            }

        # if a ray compatible worker is provided, forward the worker directly
        return {
            worker.remote(data_ref[schedule_index]): schedule_index
            for schedule_index in schedule
        }