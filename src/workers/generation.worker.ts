// src/workers/generation.worker.ts

// Importa Pyodide - il commento @ts-ignore è necessario perché l'import è un URL
// @ts-ignore
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v0.26.1/full/pyodide.js";

// Definisce i tipi per i messaggi in entrata e in uscita per chiarezza
interface WorkerInput {
  files: Record<string, Uint8Array>;
  params: Record<string, any>;
}

// Variabile globale per Pyodide
let pyodide: any;

// Funzione per inizializzare Pyodide e caricare tutto il necessario
async function initializePyodide() {
  if (pyodide) {
    return pyodide;
  }

  console.log("Inizializzazione di Pyodide...");
  self.postMessage({ type: 'STATUS', payload: 'Inizializzazione di Pyodide...' });

  pyodide = await loadPyodide({
    indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.1/full/",
  });

  console.log("Pyodide inizializzato.");
  self.postMessage({ type: 'STATUS', payload: 'Caricamento pacchetti Python...' });

  await pyodide.loadPackage(["numpy", "pandas", "openpyxl"]);

  console.log("Pacchetti caricati.");
  self.postMessage({ type: 'STATUS', payload: 'Caricamento script algoritmo...' });

  const response = await fetch('/algoritmo_orari.py');
  const pythonScript = await response.text();
  pyodide.runPython(pythonScript);

  console.log("Script Python caricato ed eseguito.");
  self.postMessage({ type: 'STATUS', payload: 'Pronto a ricevere i dati.' });

  return pyodide;
}

// Mantiene la promessa di inizializzazione per evitare race condition
const pyodideReadyPromise = initializePyodide();

// Listener per i messaggi dal thread principale
self.onmessage = async (event) => {
  const { files, params } = event.data as WorkerInput;

  try {
    // Assicura che Pyodide sia pronto
    await pyodideReadyPromise;

    // Definisce la funzione di callback per il progresso, che sarà visibile da Python
    (self as any).update_progress = (current: number, total: number) => {
      self.postMessage({ type: 'PROGRESS', payload: { current, total } });
    };

    // Converte i dizionari JS in oggetti Python (PyProxy)
    const pyFiles = pyodide.toPy(files);
    const pyParams = pyodide.toPy(params);

    // Ottiene un riferimento alla funzione wrapper Python
    const runAlgorithm = pyodide.globals.get('run_genetic_algorithm');

    // Esegue la funzione Python passando i dati e la callback
    self.postMessage({ type: 'STATUS', payload: 'Esecuzione algoritmo genetico...' });
    const results = await runAlgorithm(pyFiles, pyParams, (self as any).update_progress);

    // Converte i risultati (PyProxy) in un oggetto JS
    const jsResults = results.toJs({ dict_converter: Object.fromEntries });

    // Invia i risultati al thread principale
    self.postMessage({ type: 'COMPLETE', payload: jsResults });

  } catch (error: any) {
    console.error("Errore nel Web Worker:", error);
    // Invia un messaggio di errore al thread principale
    self.postMessage({ type: 'ERROR', payload: error.message });
  }
};
