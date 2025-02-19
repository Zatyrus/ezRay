# Get Started
```powershell
pip install ezRay
```

# Quick Start Guide
```python
from ezRay import MultiCoreExecutionTool

# configure ezRay
instance_metadata:dict = {
    'num_cpus': 4,              # number of cpus to use
    'num_gpus': 0,              # number of gpus to use
    'address': None,            # remote cluster address. None for local.
    }

# setup ezRay
MultiCore = MultiCoreExecutionTool(instance_metadata = instance_metadata)

# launch ray dashboard (optional)
MultiCore.launch_dashboard()

# define a task
def do_something(foo:int, bar:int) -> int:
    return foo + bar

# prepare your data in a dictionary. They keys work as identifiers, while the values should be dictionaries matching the function signature.
data = {
    1:{'foo' : 0, 'bar' : 1},
    2:{'foo' : 1, 'bar' : 2},
    3:{'foo' : 2, 'bar' : 3}
    }

# pass the data to ezRay
MultiCore.update_data(data)

# run the task
MultiCore.run(do_something)

# get the results
results = MultiCore.get_results()
```

## A ray.remote object can be used interchangeably with a function
```python
@ray.remote(num_cpus=1, num_gpus=0, num_returns=1)
def do_something_remtoe(foo:int, bar:int) -> int:
    return foo + bar

MultiCore.run(do_something_remote)
```