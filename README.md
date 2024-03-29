# PANDAS optimization demo

This demo demonstrates the various approaches when working with DataFrames using ***PANDAS***, ***DASK***, ***MODIN***
and ***multiprocessing*** python library. It compares the time and memory efficiency of these libraries.

### The dataset

The dataset used in this demo consists of flight arrival and departure details for all commercial flights within the
USA, from October 1987 to April 2008 and can be downloaded from
here <https://community.amstat.org/jointscsg-section/dataexpo/dataexpo2009>.

### Demo description

Gathers the system resource usage from the task runs into a ***.csv*** file and can display them in a
***plotly*** graph. ***DASK*** and ***MODIN*** tasks require a cluster for the execution, whose address can be specified
through command line options, otherwise it will be created during the program run.

### Usage

pandasOptimization.py [-h] -p
PATH [--cluster ADDRESS] [--task {pandas,dask,multiproc,modin} [{pandas,dask,multiproc,modin} ...]] [--file FILE] [--plot] [-r RUNS]

##### optional arguments:

optional arguments:

- -h, --help => Show this help message and exit.
- -p PATH, --path PATH => Path to the file with dataset.
- --cluster ADDRESS => Address of the remote cluster that should be used, if not specified, program uses a locally
  created cluster.
- --task {pandas,dask,multiproc,modin} [{pandas,dask,multiproc,modin} ...] =>
  Specify which tasks to execute, if not specified, all tasks will be run.
- --file FILE => Specify the file where the program should write usage statistics from its runs, uses usage_stats.csv as
  default if not specified.
- --plot => Display the usage statistics graph.
- -r RUNS, --runs RUNS => Specify the number of runs for each task, run once if not specified.



