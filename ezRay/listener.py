## Dependencies:
import time
from typing import Any, Dict, Tuple

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


class Listener:
    def __init__(self, DEBUG: bool = False, ListenerSleeptime: float = 0.1):
        """Initializes the Listener class.

        Args:
            DEBUG (bool, optional): Flag to enable debugging. Defaults to False.
            ListenerSleeptime (float, optional): Time to sleep between progress checks. Defaults to 0.1.
        """
        self.DEBUG = DEBUG
        self.ListenerSleeptime = ListenerSleeptime

    def silent(
        self, object_references: Dict[ray.ObjectRef, int]
        ) -> Tuple[bool, Dict[int, Any]]:
        """Silently listenes to the ray progress and retrieves the results.

        Args:
            object_references (Dict[ray.ObjectRef,int]): Dictionary containing the object references and their corresponding keys for keeping track of the progress and upholding the order of input data provided.

        Returns:
            Tuple[bool, Dict[int,Any]]: Boolean flag signaling the success or the execution, Dictionary containing the results of the execution.
        """

        try:
            # setup collection list
            pending_states: list = list(object_references.keys())
            finished_states: list = []

            if self.DEBUG:
                print("Listening to Ray Progress...")

            while len(pending_states) > 0:
                try:
                    # get the ready refs
                    finished, pending_states = ray.wait(
                        pending_states,
                        num_returns=len(pending_states),
                        timeout=1e-3,
                        fetch_local=False,
                    )

                    finished_states.extend(finished)

                except KeyboardInterrupt:
                    print("Interrupted")
                    break

                if self.ListenerSleeptime > 0:
                    time.sleep(self.ListenerSleeptime)

            # sort and return the results
            if self.DEBUG:
                print("Fetching Results...")
            finished_states = {object_references[ref]: ref for ref in finished_states}

            return True, finished_states

        except Exception as e:
            print(f"Error: {e}")
            return False, None

    def verbose(
        self, object_references: Dict[ray.ObjectRef, int]
    ) -> Tuple[bool, Dict[int, Any]]:
        """Listenes to and reports on the ray progress and system CPU and Memory. Retrieves results of successful tasks.

        Args:
            object_references (Dict[ray.ObjectRef,int]): Dictionary containing the object references and their corresponding keys for keeping track of the progress and upholding the order of input data provided.

        Returns:
            Tuple[bool, Dict[int,Any]]: Boolean flag signaling the success or the execution, Dictionary containing the results of the execution.
        """
        try:
            if self.DEBUG:
                print("Setting up progress monitors...")

            ## create progress monitors
            core_progress = tqdm(
                total=len(object_references), desc="Workers", position=1
            )
            cpu_progress = tqdm(
                total=100,
                desc="CPU usage",
                bar_format="{desc}: {percentage:3.0f}%|{bar}|",
                position=2,
            )
            mem_progress = tqdm(
                total=psutil.virtual_memory().total,
                desc="RAM usage",
                bar_format="{desc}: {percentage:3.0f}%|{bar}|",
                position=3,
            )

            # setup collection list
            pending_states: list = list(object_references.keys())
            finished_states: list = []

            if self.DEBUG:
                print("Listening to Ray Progress...")
            ## listen for progress
            while len(pending_states) > 0:
                try:
                    # get the ready refs
                    finished, pending_states = ray.wait(
                        pending_states,
                        num_returns=len(pending_states),
                        timeout=1e-3,
                        fetch_local=False,
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
                    print("Interrupted")
                    break

            # set the progress bars to success
            core_progress.colour = "green"
            cpu_progress.colour = "green"
            mem_progress.colour = "green"

            # set the progress bars to their final values
            core_progress.n = len(object_references)
            cpu_progress.n = 0
            mem_progress.n = 0

            # close the progress bars
            core_progress.close()
            cpu_progress.close()
            mem_progress.close()

            # sort and return the results
            if self.DEBUG:
                print("Fetching Results...")
            finished_states = {object_references[ref]: ref for ref in finished_states}

            if self.DEBUG:
                print("Ray Progress Complete...")

            return True, finished_states

        except Exception as e:
            print(f"Error: {e}")
            return False, None
