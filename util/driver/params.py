import attr
from labgrid.factory import target_factory
from labgrid.resource import Resource


@target_factory.reg_resource
@attr.s(eq=False)
class QEMUParams(Resource):
    overwrite: bool | None = attr.ib(
        default=False, validator=attr.validators.optional(attr.validators.instance_of(bool))
    )
