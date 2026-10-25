"""Arrow schemas derived from ledger_schemas models, the source of the Iceberg table schemas."""

import types
from collections.abc import Iterable
from datetime import date, datetime
from typing import Annotated, Any, Literal, Union, get_args, get_origin

import pyarrow as pa
from pydantic import AwareDatetime, BaseModel

TIMESTAMP = pa.timestamp("us", tz="UTC")


def _strip(annotation: Any) -> tuple[Any, bool]:
    """Unwrap Annotated and Optional; return (inner type, nullable)."""
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    if get_origin(annotation) in (Union, types.UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) != 1:
            raise TypeError(f"unsupported union: {annotation}")
        inner, _ = _strip(args[0])
        return inner, True
    return annotation, False


def _arrow_type(annotation: Any) -> pa.DataType:
    inner, _ = _strip(annotation)
    origin = get_origin(inner)
    if origin is Literal:
        values = get_args(inner)
        if not all(isinstance(v, str) for v in values):
            raise TypeError(f"only string literals are supported: {inner}")
        return pa.string()
    if origin is list:
        (item,) = get_args(inner)
        item_inner, item_nullable = _strip(item)
        return pa.list_(pa.field("element", _arrow_type(item_inner), nullable=item_nullable))
    if isinstance(inner, type) and issubclass(inner, BaseModel):
        return pa.struct(list(schema_for(inner)))
    simple: dict[Any, pa.DataType] = {
        str: pa.string(),
        int: pa.int64(),
        float: pa.float64(),
        bool: pa.bool_(),
        datetime: TIMESTAMP,
        AwareDatetime: TIMESTAMP,  # a marker class at runtime, not a datetime subclass
        date: pa.date32(),
    }
    if inner in simple:
        return simple[inner]
    raise TypeError(f"no Arrow mapping for {inner!r}")


def schema_for(model: type[BaseModel]) -> pa.Schema:
    fields = []
    for name, info in model.model_fields.items():
        _, nullable = _strip(info.annotation)
        fields.append(pa.field(name, _arrow_type(info.annotation), nullable=nullable))
    return pa.schema(fields)


def to_table(model: type[BaseModel], records: Iterable[BaseModel]) -> pa.Table:
    return pa.Table.from_pylist([r.model_dump() for r in records], schema=schema_for(model))
