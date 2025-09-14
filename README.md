# Generatore di Orari per l'Educazione Civica

Questa è un'applicazione web single-page (SPA) interamente client-side che permette di generare un calendario ottimizzato per le sostituzioni di educazione civica. L'applicazione utilizza un algoritmo genetico scritto in Python, eseguito direttamente nel browser tramite WebAssembly (Pyodide) e Web Workers per non bloccare l'interfaccia utente.

## Stack Tecnologico

-   **Frontend Framework:** React (con Vite)
-   **Linguaggio:** TypeScript
-   **UI Components:** shadcn/ui
-   **Styling:** Tailwind CSS
-   **Esecuzione Python:** Pyodide
-   **Concorrenza:** Web Workers

## Architettura

L'applicazione è composta da tre parti principali:

1.  **Thread Principale (UI):** Gestisce l'interfaccia utente, costruita con React. Raccoglie i file di input e i parametri dall'utente.
2.  **Web Worker:** Un thread separato che gestisce i calcoli pesanti. Al suo interno viene inizializzato Pyodide.
3.  **Pyodide:** Un port di CPython in WebAssembly che esegue lo script dell'algoritmo genetico con le sue dipendenze (`pandas`, `numpy`, `openpyxl`).

Il flusso di comunicazione è il seguente:
-   L'utente clicca "Genera Calendario" sull'interfaccia.
-   Il thread principale invia i file (come `Uint8Array`) e i parametri al Web Worker.
-   Il Web Worker carica lo script Python, imposta una callback di progresso e avvia l'algoritmo.
-   Lo script Python, durante l'esecuzione, chiama la funzione di callback per inviare aggiornamenti sul progresso al Worker, che a sua volta li inoltra al thread principale.
-   Al termine, il Worker invia i file di output (generati in memoria) al thread principale.
-   L'interfaccia mostra i link per il download dei risultati.

## Istruzioni per l'Uso

### Prerequisiti

-   Node.js (versione 18 o superiore)
-   npm

### 1. Installazione delle Dipendenze

Clona il repository e installa le dipendenze necessarie:

```bash
npm install
```

**Nota:** A causa di una limitazione nell'ambiente di sviluppo di questo agente, la cartella `node_modules` potrebbe non essere creata localmente. Se i comandi successivi falliscono, potrebbe essere necessario eseguire `npm install` in un ambiente Node.js standard.

### 2. Avviare il Server di Sviluppo

Per avviare l'applicazione in modalità sviluppo (con hot-reloading):

```bash
npm run dev
```

Apri il browser all'indirizzo indicato (solitamente `http://localhost:5173`).

### 3. Creare la Build di Produzione

Per creare una build ottimizzata per il deployment:

```bash
npm run build
```

I file statici verranno generati nella cartella `dist/`. Questi file possono essere deployati su qualsiasi servizio di hosting statico (es. Netlify, Vercel, GitHub Pages).
