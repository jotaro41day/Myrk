"""Conservative scheduling for independent populations; no numerical rewrite."""
from dataclasses import replace
from .ir import Instruction


def batch_populations(module):
    def block(body):
        result=[]
        for item in body:
            if item.op != 'for':
                result.append(item)
                continue
            start,end,children=item.args
            accumulator=None
            eligible=len(children) in (1,2) and children[0].op=='step'
            if eligible and len(children)==2:
                update=children[1]
                eligible=update.op=='assign'
                if eligible:
                    expr=update.args[0]
                    eligible=expr.op=='binary' and expr.data=='+' and expr.dtype=='i32'
                    if eligible:
                        left,right=expr.args
                        eligible=(left.op=='variable' and left.data==update.data
                                  and right.op=='spikes' and right.data==children[0].data[0])
                        accumulator=update.data
            if eligible:
                name,dtype=children[0].data
                result.append(Instruction('advance',item.pos,(name,dtype,accumulator),(start,end)))
            else:
                result.append(replace(item,args=(start,end,block(children))))
        return tuple(result)
    # At present step is exclusively the independent, uniform-current Izhikevich
    # operation. New neural operations/dependencies must not inherit this proof.
    return replace(module,procedures=tuple(replace(p,body=block(p.body)) for p in module.procedures))
