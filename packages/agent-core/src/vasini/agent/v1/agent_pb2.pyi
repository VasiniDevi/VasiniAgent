from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TaskState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TASK_STATE_UNSPECIFIED: _ClassVar[TaskState]
    TASK_STATE_QUEUED: _ClassVar[TaskState]
    TASK_STATE_RUNNING: _ClassVar[TaskState]
    TASK_STATE_RETRY: _ClassVar[TaskState]
    TASK_STATE_DONE: _ClassVar[TaskState]
    TASK_STATE_FAILED: _ClassVar[TaskState]
    TASK_STATE_CANCELLED: _ClassVar[TaskState]
    TASK_STATE_DEAD_LETTER: _ClassVar[TaskState]
TASK_STATE_UNSPECIFIED: TaskState
TASK_STATE_QUEUED: TaskState
TASK_STATE_RUNNING: TaskState
TASK_STATE_RETRY: TaskState
TASK_STATE_DONE: TaskState
TASK_STATE_FAILED: TaskState
TASK_STATE_CANCELLED: TaskState
TASK_STATE_DEAD_LETTER: TaskState

class RunAgentRequest(_message.Message):
    __slots__ = ("pack_id", "tenant_id", "input", "session_id", "idempotency_key", "metadata")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    PACK_ID_FIELD_NUMBER: _ClassVar[int]
    TENANT_ID_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    pack_id: str
    tenant_id: str
    input: str
    session_id: str
    idempotency_key: str
    metadata: _containers.ScalarMap[str, str]
    def __init__(self, pack_id: _Optional[str] = ..., tenant_id: _Optional[str] = ..., input: _Optional[str] = ..., session_id: _Optional[str] = ..., idempotency_key: _Optional[str] = ..., metadata: _Optional[_Mapping[str, str]] = ...) -> None: ...

class RunAgentResponse(_message.Message):
    __slots__ = ("text_chunk", "tool_call", "tool_result", "status")
    TEXT_CHUNK_FIELD_NUMBER: _ClassVar[int]
    TOOL_CALL_FIELD_NUMBER: _ClassVar[int]
    TOOL_RESULT_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    text_chunk: str
    tool_call: ToolCall
    tool_result: ToolResult
    status: AgentStatus
    def __init__(self, text_chunk: _Optional[str] = ..., tool_call: _Optional[_Union[ToolCall, _Mapping]] = ..., tool_result: _Optional[_Union[ToolResult, _Mapping]] = ..., status: _Optional[_Union[AgentStatus, _Mapping]] = ...) -> None: ...

class ToolCall(_message.Message):
    __slots__ = ("tool_id", "tool_name", "arguments_json")
    TOOL_ID_FIELD_NUMBER: _ClassVar[int]
    TOOL_NAME_FIELD_NUMBER: _ClassVar[int]
    ARGUMENTS_JSON_FIELD_NUMBER: _ClassVar[int]
    tool_id: str
    tool_name: str
    arguments_json: str
    def __init__(self, tool_id: _Optional[str] = ..., tool_name: _Optional[str] = ..., arguments_json: _Optional[str] = ...) -> None: ...

class ToolResult(_message.Message):
    __slots__ = ("tool_id", "success", "result_json", "error")
    TOOL_ID_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    RESULT_JSON_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    tool_id: str
    success: bool
    result_json: str
    error: str
    def __init__(self, tool_id: _Optional[str] = ..., success: bool = ..., result_json: _Optional[str] = ..., error: _Optional[str] = ...) -> None: ...

class AgentStatus(_message.Message):
    __slots__ = ("task_id", "state", "pack_id", "pack_version")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    PACK_ID_FIELD_NUMBER: _ClassVar[int]
    PACK_VERSION_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    state: TaskState
    pack_id: str
    pack_version: str
    def __init__(self, task_id: _Optional[str] = ..., state: _Optional[_Union[TaskState, str]] = ..., pack_id: _Optional[str] = ..., pack_version: _Optional[str] = ...) -> None: ...

class GetAgentStatusRequest(_message.Message):
    __slots__ = ("task_id", "tenant_id")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    TENANT_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    tenant_id: str
    def __init__(self, task_id: _Optional[str] = ..., tenant_id: _Optional[str] = ...) -> None: ...

class CancelAgentRequest(_message.Message):
    __slots__ = ("task_id", "tenant_id")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    TENANT_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    tenant_id: str
    def __init__(self, task_id: _Optional[str] = ..., tenant_id: _Optional[str] = ...) -> None: ...

class CancelAgentResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: bool = ...) -> None: ...
