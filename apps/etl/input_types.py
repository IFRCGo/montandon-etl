from typing import List

import strawberry


@strawberry.input
class PipelineRetriggerInput:
    trace_id: List[int]


@strawberry.input
class TransformRetriggerInput:
    transform_id: List[int]
