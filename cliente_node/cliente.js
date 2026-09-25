// Segundo cliente de Flota escrito en Node.js (opcional O5).
// Usa el mismo flota.proto que el servidor en Python, asi se ve que el contrato no depende del lenguaje
const grpc = require("@grpc/grpc-js");
const protoLoader = require("@grpc/proto-loader");

const HOST = process.env.GRPC_FLOTA_HOST || "localhost:50051";
const TIMEOUT_MS = 2000;

// proto-loader lee el .proto al ejecutar, no genera codigo antes como grpc_tools en Python
const definicion = protoLoader.loadSync(__dirname + "/proto/flota.proto", {
  keepCase: true,
  longs: String,
  defaults: true,
});
const flota = grpc.loadPackageDefinition(definicion).flota.v1;
const cliente = new flota.ServicioFlota(HOST, grpc.credentials.createInsecure());

const plazo = () => new Date(Date.now() + TIMEOUT_MS);

function listarFlota() {
  // ListarFlota es server streaming, cada evento "data" es un camion que llega apenas Flota lo manda
  return new Promise((resolve, reject) => {
    console.log("== ListarFlota (server streaming)");
    const stream = cliente.ListarFlota({}, { deadline: plazo() });
    stream.on("data", (camion) => {
      const rutas = camion.rutas.map((r) => `${r.origen}->${r.destino} ${r.capacidad_disponible_kg} kg`);
      console.log(`  ${camion.camion_id}: ${rutas.join(", ")}`);
    });
    stream.on("end", resolve);
    stream.on("error", reject);
  });
}

function llamar(metodo, request) {
  return new Promise((resolve, reject) => {
    cliente[metodo](request, { deadline: plazo() }, (error, respuesta) => (error ? reject(error) : resolve(respuesta)));
  });
}

async function main() {
  await listarFlota();

  console.log("== BuscarDisponibles Concepcion -> Chillan, minimo 1000 kg");
  const disponibles = await llamar("BuscarDisponibles", { origen: "Concepcion", destino: "Chillan", carga_minima_kg: 1000 });
  disponibles.camiones.forEach((c) => console.log(`  ${c.camion_id}: ${c.capacidad_disponible_kg} kg libres`));

  console.log("== ConsultarCamion CAM-99 (no existe)");
  try {
    await llamar("ConsultarCamion", { camion_id: "CAM-99" });
  } catch (error) {
    // Los codigos de estado de gRPC son los mismos en cualquier lenguaje, 5 es NOT_FOUND
    console.log(`  error ${grpc.status[error.code]}: ${error.details}`);
  }
}

main().catch((error) => {
  console.error(`Fallo la llamada a Flota: ${grpc.status[error.code] || ""} ${error.details || error.message}`);
  process.exit(1);
});
