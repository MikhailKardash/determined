import datetime
from argparse import ONE_OR_MORE, Namespace
from typing import Any, List, Union

from determined import cli
from determined.cli import render
from determined.common import api, yaml
from determined.common.api import authentication, bindings
from determined.common.declarative_argparse import Arg, Cmd, Group
from determined.common.util import parse_protobuf_timestamp


def parse_jobv2_resp(
    resp: bindings.v1GetJobsV2Response,
) -> List[Union[bindings.v1Job, bindings.v1LimitedJob]]:
    jobs_nullable = [j.full if j.full is not None else j.limited for j in resp.jobs]
    jobs: List[Union[bindings.v1Job, bindings.v1LimitedJob]] = []
    for j in jobs_nullable:
        if j is not None:
            jobs.append(j)
    return jobs


@authentication.required
def ls(args: Namespace) -> None:
    session = cli.setup_session(args)
    pools = bindings.get_GetResourcePools(cli.setup_session(args))
    is_priority = check_is_priority(pools, args.resource_pool)

    order_by = bindings.v1OrderBy.ASC if not args.reverse else bindings.v1OrderBy.DESC

    def get_with_offset(offset: int) -> bindings.v1GetJobsV2Response:
        return bindings.get_GetJobsV2(
            session,
            resourcePool=args.resource_pool,
            offset=offset,
            limit=args.limit,
            orderBy=order_by,
        )

    paginated_resps = api.read_paginated(get_with_offset, offset=args.offset, pages=args.pages)
    jobs = [j for r in paginated_resps for j in parse_jobv2_resp(r)]

    if args.yaml or args.json:
        data = {
            "jobs": [v.to_json() for v in jobs],
        }
        if args.yaml:
            print(yaml.safe_dump(data, default_flow_style=False))
        elif args.json:
            render.print_json(data)
        return

    headers = [
        "#",
        "ID",
        "Type",
        "Job Name",
        "Priority" if is_priority else "Weight",
        "Submitted",
        "Slots (acquired/needed)",
        "State",
        "User",
    ]

    def computed_job_name(job: bindings.v1Job) -> str:
        if job.type == bindings.jobv1Type.EXPERIMENT:
            return f"{job.name} ({job.entityId})"
        else:
            return job.name

    values = [
        [
            j.summary.jobsAhead if j.summary is not None and j.summary.jobsAhead > -1 else "N/A",
            j.jobId,
            j.type.value,
            computed_job_name(j) if isinstance(j, bindings.v1Job) else render.OMITTED_VALUE,
            j.priority if is_priority else j.weight,
            parse_protobuf_timestamp(j.submissionTime).astimezone(datetime.timezone.utc)
            if isinstance(j, bindings.v1Job)
            else render.OMITTED_VALUE,
            f"{j.allocatedSlots}/{j.requestedSlots}",
            j.summary.state.value if j.summary is not None else "N/A",
            j.username if isinstance(j, bindings.v1Job) else render.OMITTED_VALUE,
        ]
        for j in jobs
    ]
    render.tabulate_or_csv(headers, values, as_csv=args.csv)


@authentication.required
def update(args: Namespace) -> None:
    update = bindings.v1QueueControl(
        jobId=args.job_id,
        priority=args.priority,
        weight=args.weight,
        resourcePool=args.resource_pool,
        behindOf=args.behind_of,
        aheadOf=args.ahead_of,
    )
    bindings.post_UpdateJobQueue(
        cli.setup_session(args), body=bindings.v1UpdateJobQueueRequest(updates=[update])
    )


@authentication.required
def process_updates(args: Namespace) -> None:
    session = cli.setup_session(args)
    for arg in args.operation:
        inputs = validate_operation_args(arg)
        _single_update(session=session, **inputs)


def _single_update(
    job_id: str,
    session: api.Session,
    priority: str = "",
    weight: str = "",
    resource_pool: str = "",
    behind_of: str = "",
    ahead_of: str = "",
) -> None:
    update = bindings.v1QueueControl(
        jobId=job_id,
        priority=int(priority) if priority != "" else None,
        weight=int(weight) if weight != "" else None,
        resourcePool=resource_pool if resource_pool != "" else None,
        behindOf=behind_of if behind_of != "" else None,
        aheadOf=ahead_of if ahead_of != "" else None,
    )
    bindings.post_UpdateJobQueue(session, body=bindings.v1UpdateJobQueueRequest(updates=[update]))


def check_is_priority(pools: bindings.v1GetResourcePoolsResponse, resource_pool: str) -> bool:
    if pools.resourcePools is None:
        raise ValueError(f"No resource pools found checking scheduler type of {resource_pool}")

    for pool in pools.resourcePools:
        if (resource_pool is None and pool.defaultComputePool) or resource_pool == pool.name:
            return pool.schedulerType == bindings.v1SchedulerType.PRIORITY
    raise ValueError(f"Pool {resource_pool} not found")


def validate_operation_args(operation: str) -> dict:
    valid_cmds = ("priority", "weight", "resource_pool", "ahead_of", "behind_of")
    replacements = {
        "resource-pool": "resource_pool",
        "ahead-of": "ahead_of",
        "behind-of": "behind_of",
    }
    args = {}
    values = operation.split(".")
    if len(values) != 2:
        raise ValueError(
            f"Job {values[0]} and its operation have an invalid format. "
            f"Please ensure the update is formatted as <jobID>.<operation>=<value>."
        )
    args["job_id"] = values[0]
    operand = values[1].split("=")
    if len(operand) != 2:
        raise ValueError(
            f"The operation for job {values[0]} has invalid format. "
            f"Please ensure the operation is formatted as <operation>=<value>."
        )

    if operand[0] not in valid_cmds and operand[0] not in replacements:
        raise ValueError(
            f"Invalid operation {operand[0]} specified for job {values[0]}. "
            f"Supported commands include: {valid_cmds}."
        )

    args[replacements.get(operand[0], operand[0])] = operand[1]

    return args


args_description = [
    Cmd(
        "j|ob",
        None,
        "manage jobs",
        [
            Cmd(
                "list ls",
                ls,
                "list jobs",
                [
                    Arg(
                        "-p",
                        "--resource-pool",
                        type=str,
                        help="The target resource pool, if any.",
                    ),
                    *cli.make_pagination_args(limit=100, supports_reverse=True),
                    Group(
                        cli.output_format_args["json"],
                        cli.output_format_args["yaml"],
                        cli.output_format_args["table"],
                        cli.output_format_args["csv"],
                    ),
                ],
                is_default=True,
            ),
            Cmd(
                "u|pdate",
                update,
                "update job",
                [
                    Arg("job_id", type=str, help="The target job ID"),
                    Group(
                        Arg(
                            "-p",
                            "--priority",
                            type=int,
                            help="The new priority. Exclusive to priority scheduler.",
                        ),
                        Arg(
                            "-w",
                            "--weight",
                            type=float,
                            help="The new weight. Exclusive to fair_share scheduler.",
                        ),
                        Arg(
                            "--resource-pool",
                            type=str,
                            help="The target resource pool to move the job to.",
                        ),
                        Arg(
                            "--ahead-of",
                            type=str,
                            help="The job ID of the job to be put ahead of in the queue.",
                        ),
                        Arg(
                            "--behind-of",
                            type=str,
                            help="The job ID of the job to be put behind in the queue.",
                        ),
                    ),
                ],
            ),
            Cmd(
                "update-batch",
                process_updates,
                "batch update jobs",
                [
                    Arg(
                        "operation",
                        nargs=ONE_OR_MORE,
                        type=str,
                        help="The target job ID(s) and target operation(s), formatted as "
                        "<jobID>.<operation>=<value>. Operations include priority, weight, "
                        "resource-pool, ahead-of, and behind-of.",
                    )
                ],
            ),
        ],
    ),
]  # type: List[Any]
