# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import os
from datetime import timedelta

import torch


def _warn_overwrite_env(env, val):
    if env in os.environ:
        logger.warning(
            f"ENV[{env}] = {os.environ[env]} will be overridden to {val} based on job config"
        )
    os.environ[env] = val


TRACE_BUFFER_SIZE = "TORCH_NCCL_TRACE_BUFFER_SIZE"
TRACE_FILE = "TORCH_NCCL_DEBUG_INFO_TEMP_FILE"
DUMP_ON_TIMEOUT = "TORCH_NCCL_DUMP_ON_TIMEOUT"
ASYNC_ERROR_HANDLING = "TORCH_NCCL_ASYNC_ERROR_HANDLING"
SKIP_CLEANUP = "3"


def init_distributed(job_config):
    # FlightRecorder is incompatible with =1 mode where watchdog aborts work, must use =3 (skipcleanup)
    # to get flight recorder dumps. See https://github.com/pytorch/pytorch/issues/121055
    # This could be done only when flight recorder is enabled, but its nice to be consistent to avoid subtle
    # behavior differences
    _warn_overwrite_env(ASYNC_ERROR_HANDLING, SKIP_CLEANUP)

    # enable torch nccl flight recorder in the mode that would dump files if timeout is detected
    _warn_overwrite_env(TRACE_BUFFER_SIZE, str(job_config.comm.trace_buf_size))
    if job_config.comm.trace_buf_size > 0:
        # dump on timeout by default if trace buffer is enabled
        _warn_overwrite_env(DUMP_ON_TIMEOUT, "1")
        dump_dir = f"{job_config.job.dump_folder}/comm_trace"
        os.makedirs(dump_dir, exist_ok=True)
        _warn_overwrite_env(TRACE_FILE, f"{dump_dir}/rank_")

    torch.distributed.init_process_group(
        "nccl", timeout=timedelta(seconds=job_config.comm.init_timeout_seconds)
    )

    # to mitigate the memory issue that collectives using
    # async_op=True hold memory longer than they should
    # such as those in tensor parallelism
    os.environ["TORCH_NCCL_AVOID_RECORD_STREAMS"] = "1"