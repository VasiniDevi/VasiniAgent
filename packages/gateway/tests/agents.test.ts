import { describe, it, expect, beforeAll, afterAll, vi } from "vitest";
import { buildServer } from "../src/server.js";
import type { FastifyInstance } from "fastify";

describe("Gateway REST API", () => {
  let server: FastifyInstance;

  beforeAll(async () => {
    server = await buildServer({ grpcTarget: "localhost:50051" });
  });

  afterAll(async () => {
    await server.close();
  });

  describe("POST /api/v1/agents/:packId/run", () => {
    it("returns 400 without X-Tenant-ID header", async () => {
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        payload: { input: "Hello" },
      });
      expect(res.statusCode).toBe(400);
      const body = JSON.parse(res.payload);
      expect(body.code).toBe("MISSING_TENANT");
      expect(body.message).toContain("X-Tenant-ID");
      expect(body.trace_id).toBeDefined();
    });

    it("returns 400 without input in body", async () => {
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        headers: { "x-tenant-id": "tenant-123" },
        payload: {},
      });
      expect(res.statusCode).toBe(400);
      const body = JSON.parse(res.payload);
      expect(body.code).toBe("MISSING_INPUT");
    });

    it("returns 400 without X-Idempotency-Key header", async () => {
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        headers: { "x-tenant-id": "tenant-123" },
        payload: { input: "Hello" },
      });
      expect(res.statusCode).toBe(400);
      const body = JSON.parse(res.payload);
      expect(body.code).toBe("MISSING_IDEMPOTENCY_KEY");
    });

    it("returns 202 with valid request (mocked gRPC)", async () => {
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        headers: {
          "x-tenant-id": "tenant-123",
          "x-idempotency-key": "idem-001",
        },
        payload: { input: "Write a Python function" },
      });
      expect(res.statusCode).toBe(202);
      const body = JSON.parse(res.payload);
      expect(body.task_id).toBeDefined();
      expect(body.status).toBe("queued");
    });
  });

  describe("GET /api/v1/agents/status/:taskId", () => {
    it("returns 400 without tenant header", async () => {
      const res = await server.inject({
        method: "GET",
        url: "/api/v1/agents/status/task-123",
      });
      expect(res.statusCode).toBe(400);
      const body = JSON.parse(res.payload);
      expect(body.code).toBe("MISSING_TENANT");
    });

    it("returns task status with tenant header", async () => {
      const res = await server.inject({
        method: "GET",
        url: "/api/v1/agents/status/task-123",
        headers: { "x-tenant-id": "tenant-123" },
      });
      expect([200, 404]).toContain(res.statusCode);
    });
  });

  describe("Correlation headers", () => {
    it("injects X-Request-ID in response", async () => {
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        headers: {
          "x-tenant-id": "tenant-123",
          "x-idempotency-key": "idem-002",
        },
        payload: { input: "Hello" },
      });
      expect(res.headers["x-request-id"]).toBeDefined();
    });

    it("preserves provided X-Request-ID", async () => {
      const traceId = "trace-abc-123";
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        headers: {
          "x-tenant-id": "tenant-123",
          "x-idempotency-key": "idem-003",
          "x-request-id": traceId,
        },
        payload: { input: "Hello" },
      });
      expect(res.headers["x-request-id"]).toBe(traceId);
    });

    it("includes trace_id in error responses", async () => {
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        headers: { "x-request-id": "trace-err-1" },
        payload: { input: "Hello" },
      });
      const body = JSON.parse(res.payload);
      expect(body.trace_id).toBe("trace-err-1");
    });
  });

  describe("Health and readiness", () => {
    it("GET /health returns 200", async () => {
      const res = await server.inject({
        method: "GET",
        url: "/health",
      });
      expect(res.statusCode).toBe(200);
    });

    it("GET /ready returns 200", async () => {
      const res = await server.inject({
        method: "GET",
        url: "/ready",
      });
      expect(res.statusCode).toBe(200);
      const body = JSON.parse(res.payload);
      expect(body.status).toBe("ready");
    });
  });

  describe("Standardized error format", () => {
    it("all errors have code, message, trace_id", async () => {
      const res = await server.inject({
        method: "POST",
        url: "/api/v1/agents/senior-python-dev/run",
        payload: {},
      });
      const body = JSON.parse(res.payload);
      expect(body).toHaveProperty("code");
      expect(body).toHaveProperty("message");
      expect(body).toHaveProperty("trace_id");
    });
  });
});
