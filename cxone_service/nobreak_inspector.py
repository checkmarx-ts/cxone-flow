from cxone_api.high.policies import PolicyViolationInspector, PolicyViolationDescriptor
from typing import List


class NoBreakPolicyViolationInspector(PolicyViolationInspector):
    @property
    async def break_build(self) -> bool:
        return False
