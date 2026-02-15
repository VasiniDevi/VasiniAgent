export interface ApiError {
  code: string;
  message: string;
  trace_id: string;
  tenant_id?: string;
}

export function makeError(
  code: string,
  message: string,
  traceId: string,
  tenantId?: string
): ApiError {
  return {
    code,
    message,
    trace_id: traceId,
    ...(tenantId ? { tenant_id: tenantId } : {}),
  };
}
