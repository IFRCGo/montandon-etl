from typing import List

import strawberry


@strawberry.input
class PipelineRetriggerInput:
    trace_ids: List[strawberry.ID]


@strawberry.input
class TransformRetriggerInput:
    transform_ids: List[strawberry.ID]
