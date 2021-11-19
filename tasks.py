
import resource
from argparse import Namespace
from resource import getrusage, RUSAGE_SELF
from typing import Tuple
import timeit as ti
from glob import glob
from multiprocessing import Pool, Process, Queue

import numpy as np
import pandas as pd

import modin.pandas as mpd

from distributed import Client
import dask.dataframe as dd
from dask_memusage import install
from dask.distributed import performance_report


def set_usage() -> int:
    """Sets the parameter for getrusage function.

    :return: Parameter for getrusage.
    """
    return RUSAGE_SELF


_dtype = {'ActualElapsedTime': 'float64',
          'ArrDelay': 'float64',
          'ArrTime': 'float64',
          'DepDelay': 'float64',
          'DepTime': 'float64',
          'Distance': 'float64',
          'CRSElapsedTime': 'float64',
          'CancellationCode': 'object',
          'TailNum': 'object',
          'AirTime': 'float64',
          'TaxiIn': 'float64',
          'TaxiOut': 'float64',
          'CRSDepTime': 'string'
          }

cols = ['Year', 'Month', 'DayofMonth', 'DayOfWeek', 'CRSDepTime', 'DepDelay', 'CRSArrTime', 'ArrDelay', 'Origin',
        'Dest']


def format_usage(usage: resource.struct_rusage) -> int:
    """Reformat usage statistics data.

    :param usage: Resource usage data.
    :return: Reformatted resource usage data.
    """

    return usage.ru_maxrss


def manage_subprocess(args: Namespace, task: str) -> Tuple[str, int, float]:
    """Spawns a subprocess and executes the specified task in it.

    :param args: Parsed command line arguments.
    :param task: Task name.
    :return: Resource usage stats for the task.
    """

    functions = {
        u'pandas': pandas_main,
        u'modin': modin_main,
        u'multiproc': multiproc_main,
        u'dask': dask_main,
    }

    # execute the subprocess
    queue = Queue()
    p = Process(target=functions[task], args=(args, queue), name=task)
    p.start()
    p.join()
    p.close()

    # get usage data from queue
    mem_usage = queue.get()
    duration = queue.get()
    queue.close()

    return task, mem_usage, duration


def pandas_main(args: Namespace, queue: Queue):
    """Executes the pandas task on file(s).

    :param args: Parsed command line arguments.
    :param queue: Queue for subprocess data storing.
    """

    print(u'PANDAS started...')
    start_time = ti.default_timer()

    files = glob(args.path)
    if len(files) == 1:
        pandas_single(files[0])
    elif len(files) > 1:
        pandas_more(files)
    else:
        raise FileNotFoundError(u'Something is wrong with the files!')

    # gather usage data
    duration = ti.default_timer() - start_time
    mem_usage = format_usage(getrusage(set_usage()))
    queue.put(mem_usage)
    queue.put(duration)


def pandas_single(file: str):
    """Execute the pandas task on a single data file.

    :param file: Path to the file containing task data.
    """

    df = pd.read_csv(file, dtype=_dtype, usecols=cols)
    result = df['DepDelay'].mean()
    print(u'Dep avg is {}'.format(result))
    df.head()


def pandas_more(files: list):
    """Executes the pandas task on multiple data files.

    :param files: Path to the data files.
    """

    sums, counts = [], []
    for file in files:
        df = pd.read_csv(file, dtype=_dtype, usecols=cols)
        sums.append(df['DepDelay'].sum())
        counts.append(df['DepDelay'].count())
    print(u'Dep avg is {}'.format(sum(sums) / sum(counts)))


def dask_main(args: Namespace, queue: Queue):
    """Executes the dask task on the cluster.

    :param args: Parsed command line arguments.
    :param queue: Queue for subprocess data storing.
    """

    # cluster start/bind
    if args.cluster is None:
        client = Client()
    else:
        client = Client(args.cluster)

    print('DASK started...')
    start_time = ti.default_timer()
    # print(client.dashboard_link)

    # with performance_report('dask_report.html'):
    #     dask_task(args.path)

    dask_task(args.path)

    # gather usage data
    mem_usage = format_usage(getrusage(set_usage()))
    duration = ti.default_timer() - start_time
    queue.put(mem_usage)
    queue.put(duration)

    # cluster close if it was locally started
    if args.cluster is None:
        client.close()


def dask_task(files: str):
    """Runs dask tasks on the specified data file.

    :param files: Path to the data file(s) for task.
    """

    df = dd.read_csv(files, dtype=_dtype, usecols=cols)
    result = df['DepDelay'].mean().compute()
    df.head()
    print('Dep avg is {}'.format(result))


def multiproc_main(args: Namespace, queue: Queue):
    """Executes the multiprocessing task on file(s).

    :param args: Parsed command line arguments.
    :param queue: Queue for subprocess data storing.
    """

    # todo try to improve multiprocessing logic and performance

    print('MULTIPROC started...')
    start_time = ti.default_timer()

    files = glob(args.path)
    if len(files) == 1:
        multiproc_single(files[0])
    elif len(files) > 1:
        multiproc_more(files)
    else:
        raise FileNotFoundError(u'Something is wrong with the files!')

    # gather usage data
    duration = ti.default_timer() - start_time
    mem_usage = format_usage(getrusage(set_usage()))
    queue.put(mem_usage)
    queue.put(duration)


def multiproc_single(file: str, control_print: bool = True) -> Tuple[int, int]:
    """Executes the task with Pool of processes.

    :param control_print: Determine if control output should be printed.
    :param file: Path to the data file for task.
    """

    num_cores = 4
    df = pd.read_csv(file, dtype=_dtype, usecols=cols)
    df_split = np.array_split(df, num_cores)

    del_sum, del_cnt = 0, 0
    with Pool(num_cores) as pool:
        output = pool.map(multiproc_task, df_split)
        for x, y in output:
            del_sum += x
            del_cnt += y
        if control_print:
            print('Dep avg is {}'.format(del_sum / del_cnt))

    return del_sum, del_cnt


def multiproc_more(files: list):
    """Executes the task over multiple files.

    :param files: Path to the files.
    """

    sums, counts = [], []

    for file in files:
        del_sum, del_cnt = multiproc_single(file, False)
        sums.append(del_sum)
        counts.append(del_cnt)

    print('Dep avg is {}'.format(sum(sums) / sum(counts)))


def multiproc_task(df: pd.DataFrame) -> Tuple[int, int]:
    """Runs multiprocessing task on the specified part of the DataFrame.

    :param df: Part of the DataFrame.
    :return: Tuple of intermediate task results.
    """

    del_sum = df['DepDelay'].sum()
    del_cnt = df['DepDelay'].count()
    return del_sum, del_cnt


def modin_main(args: Namespace, queue: Queue):
    """Executes the modin task on the cluster.

    :param args: Parsed command line arguments.
    :param queue: Queue for subprocess data storing.
    """

    # cluster start/bind
    files = glob(args.path)
    if args.cluster is None:
        client = Client()
    else:
        client = Client(args.cluster)

    start_time = ti.default_timer()
    print('MODIN started...')
    if len(files) == 1:
        modin_single(files[0])
    elif len(files) > 1:
        modin_more(files)

    # gather usage data
    mem_usage = format_usage(getrusage(set_usage()))
    duration = ti.default_timer() - start_time
    queue.put(mem_usage)
    queue.put(duration)

    # cluster close if it was locally started
    if args.cluster is None:
        client.close()


def modin_single(file: str):
    """Runs modin task on the specified data file.

    :param file: Path to the data file(s) for task.
    """

    df = mpd.read_csv(file, dtype=_dtype, usecols=cols)
    df.head()
    result = df['DepDelay'].mean()
    print('Dep avg is {}'.format(result))


def modin_more(files: list):
    """Executes the modin task on multiple data files.

    :param files: Path to the data files.
    """

    sums, counts = [], []
    for file in files:
        df = mpd.read_csv(file, dtype=_dtype, usecols=cols)
        sums.append(df['DepDelay'].sum())
        counts.append(df['DepDelay'].count())
    print(u'Dep avg is {}'.format(sum(sums) / sum(counts)))
