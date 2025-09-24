## Dependencies:
import time
from typing import Any, Dict, Tuple

import psutil
import ray

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
    def __init__(self, DEBUG: bool = False):
        """Initializes the Listener class.

        Args:
            DEBUG (bool, optional): Flag to enable debugging. Defaults to False.
        """
        self.DEBUG = DEBUG

    def compose_listener(
        self, object_references: Dict[ray.ObjectRef, int], verbose: bool = True
    ) -> Tuple[bool, Dict[int, Any]]:
        """Listenes to and reports on the ray progress and system CPU and Memory. Retrieves results of successful tasks.

        Args:
            object_references (Dict[ray.ObjectRef,int]): Dictionary containing the object references and their corresponding keys for keeping track of the progress and upholding the order of input data provided.
            verbose (bool, optional): Flag to enable verbose output. Defaults to True.

        Returns:
            Tuple[bool, Dict[int,Any]]: Boolean flag signaling the success or the execution, Dictionary containing the results of the execution.
        """
        try:
            if self.DEBUG:
                print("Setting up progress monitors...")

            ## create progress monitors
            core_progress = tqdm(
                disable=not verbose,
                total=len(object_references),
                desc="Workers",
                position=1,
                miniters=1,
            )
            cpu_progress = tqdm(
                disable=not verbose,
                total=100,
                desc="CPU usage",
                bar_format="{desc}: {percentage:3.0f}%|{bar}|",
                position=2,
            )
            mem_progress = tqdm(
                disable=not verbose,
                total=psutil.virtual_memory().total,
                desc="RAM usage",
                bar_format="{desc}: {percentage:3.0f}%|{bar}|",
                position=3,
                miniters=1,
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

    def silent(
        self, object_references: Dict[ray.ObjectRef, int]
    ) -> Tuple[bool, Dict[int, Any]]:
        """Silently listenes to the ray progress and retrieves the results.

        Args:
            object_references (Dict[ray.ObjectRef,int]): Dictionary containing the object references and their corresponding keys for keeping track of the progress and upholding the order of input data provided.

        Returns:
            Tuple[bool, Dict[int,Any]]: Boolean flag signaling the success or the execution, Dictionary containing the results of the execution.
        """
        ## SILENT MODE
        return self.compose_listener(object_references, verbose=False)

    def verbose(
        self, object_references: Dict[ray.ObjectRef, int]
    ) -> Tuple[bool, Dict[int, Any]]:
        """Listenes to and reports on the ray progress and system CPU and Memory. Retrieves results of successful tasks.

        Args:
            object_references (Dict[ray.ObjectRef,int]): Dictionary containing the object references and their corresponding keys for keeping track of the progress and upholding the order of input data provided.

        Returns:
            Tuple[bool, Dict[int,Any]]: Boolean flag signaling the success or the execution, Dictionary containing the results of the execution.
        """
        ## VERBOSE MODE
        return self.compose_listener(object_references, verbose=True)
