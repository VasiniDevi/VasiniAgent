import { buildServer } from "./server.js";

const HOST = process.env.HOST ?? "0.0.0.0";
const PORT = parseInt(process.env.PORT ?? "3000", 10);
const GRPC_TARGET = process.env.GRPC_TARGET ?? "localhost:50051";

async function main(): Promise<void> {
  const server = await buildServer({ grpcTarget: GRPC_TARGET, host: HOST, port: PORT });
  await server.listen({ host: HOST, port: PORT });
  console.log(`Vasini Gateway listening on ${HOST}:${PORT}`);
}

main().catch((err) => {
  console.error("Failed to start gateway:", err);
  process.exit(1);
});
