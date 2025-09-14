"use client";

import { useState, useEffect, useRef } from "react";
import { useDropzone } from "react-dropzone";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Checkbox } from "@/components/ui/checkbox";
import { DatePicker } from "@/components/ui/date-picker";
import { UploadCloud, File as FileIcon, AlertCircle } from "lucide-react";
import { format } from "date-fns";
import { toast } from "sonner";
import { GenerationProgress } from "./GenerationProgress";
import { ResultsDisplay } from "./ResultsDisplay";

// Types
type AppStatus = 'idle' | 'processing' | 'success' | 'error';
interface GenerationResults {
  calendar_csv: string;
  teachersLost_csv: string;
  orario_classi_xlsx: Uint8Array;
  orario_docenti_xlsx: Uint8Array;
  final_fitness: number;
}

const fileInputConfigs = [
  { id: "classes", label: "Orari delle Classi (.xlsx)", description: "File con gli orari settimanali delle classi." },
  { id: "civics_teachers", label: "Docenti di Ed. Civica (.xlsx)", description: "File con l'elenco dei docenti e le loro classi." },
  { id: "availability", label: "Disponibilità Docenti (.xlsx)", description: "File con le disponibilità orarie dei docenti." },
  { id: "closures", label: "Chiusure Scolastiche (.xlsx)", description: "File con i giorni di chiusura della scuola." },
];

function FileUploader({ id, label, file, setFile, disabled }: { id: string; label: string; file: File | null; setFile: (id: string, file: File | null) => void; disabled: boolean; }) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (acceptedFiles) => setFile(id, acceptedFiles[0] || null),
    accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'], 'application/vnd.ms-excel': ['.xls'] },
    maxFiles: 1,
    disabled,
  });

  return (
    <div>
      <Label>{label}</Label>
      <div {...getRootProps()} className={`mt-2 flex justify-center rounded-lg border border-dashed border-input px-6 py-10 transition-colors ${disabled ? 'bg-muted/50' : isDragActive ? "border-primary bg-primary/10" : "hover:border-primary/50"}`}>
        <div className="text-center">
          {file ? (
            <div className="flex flex-col items-center gap-2"><FileIcon className="h-10 w-10 text-muted-foreground" /><p className="font-semibold text-sm">{file.name}</p><button disabled={disabled} onClick={(e) => { e.stopPropagation(); setFile(id, null); }} className="text-red-500 hover:text-red-700 text-xs font-bold disabled:opacity-50">Rimuovi</button></div>
          ) : (
            <><UploadCloud className="mx-auto h-10 w-10 text-muted-foreground" /><p className="mt-4 text-sm text-muted-foreground">{isDragActive ? "Rilascia il file qui" : "Trascina o clicca per caricare"}</p><p className="text-xs text-muted-foreground/80">XLSX, XLS</p><input {...getInputProps()} className="sr-only" /></>
          )}
        </div>
      </div>
    </div>
  );
}

export function GenerationForm() {
  const [status, setStatus] = useState<AppStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState('');
  const [results, setResults] = useState<GenerationResults | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [files, setFiles] = useState<Record<string, File | null>>({ classes: null, civics_teachers: null, availability: null, closures: null });
  const [params, setParams] = useState({
    data_inizio: new Date('2024-10-15'), data_fine: new Date('2025-06-10'), ore_tot_civics: 30, num_generazioni: 400, popolazione_size: 500,
    probabilita_mutazione: 0.5, probabilita_crossover: 0.8, elitismo_rate: 0.01, early_stopping_n: 20, allow_teacher_replace_self: false,
  });

  const workerRef = useRef<Worker | null>(null);

  useEffect(() => {
    // Inizializza il worker
    workerRef.current = new Worker(new URL('../workers/generation.worker.ts', import.meta.url), { type: 'module' });

    workerRef.current.onmessage = (event) => {
      const { type, payload } = event.data;
      switch (type) {
        case 'STATUS': setStatusText(payload); break;
        case 'PROGRESS': setProgress((payload.current / payload.total) * 100); break;
        case 'COMPLETE':
          setStatus('success');
          setResults(payload);
          toast.success("Generazione completata con successo!");
          break;
        case 'ERROR':
          setStatus('error');
          setError(payload);
          toast.error("Si è verificato un errore durante la generazione.");
          break;
      }
    };

    return () => workerRef.current?.terminate();
  }, []);

  const handleFileChange = (id: string, file: File | null) => setFiles(prev => ({ ...prev, [id]: file }));
  const handleParamChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { id, value, type, checked } = e.target;
    setParams(prev => ({ ...prev, [id]: type === 'checkbox' ? checked : parseFloat(value) }));
  };
  const handleSliderChange = (id: string, value: number[]) => setParams(prev => ({ ...prev, [id]: value[0] }));
  const handleDateChange = (id: 'data_inizio' | 'data_fine', date: Date | undefined) => date && setParams(prev => ({ ...prev, [id]: date }));

  const resetState = () => {
      setStatus('idle');
      setProgress(0);
      setStatusText('');
      setResults(null);
      setError(null);
      setFiles({ classes: null, civics_teachers: null, availability: null, closures: null });
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (Object.values(files).some(f => !f)) {
      toast.error("Per favore, carica tutti e 4 i file richiesti.");
      return;
    }

    setStatus('processing');
    setError(null);
    setResults(null);
    setProgress(0);
    setStatusText("Preparazione dei file...");

    const fileContents: Record<string, Uint8Array> = {};
    for (const key in files) {
      const buffer = await files[key]!.arrayBuffer();
      fileContents[key] = new Uint8Array(buffer);
    }

    const formattedParams = { ...params, data_inizio_str: format(params.data_inizio, "dd/MM/yyyy"), data_fine_str: format(params.data_fine, "dd/MM/yyyy") };
    // @ts-ignore
    delete formattedParams.data_inizio; delete formattedParams.data_fine;

    workerRef.current?.postMessage({ files: fileContents, params: formattedParams });
  };

  const isProcessing = status === 'processing';
  const isFormValid = Object.values(files).every(file => file !== null);

  if (isProcessing) return <GenerationProgress status={statusText} progress={progress} />;
  if (status === 'success' && results) return <ResultsDisplay results={results} onReset={resetState} />;
  if (status === 'error') return (
      <Card className="border-destructive">
        <CardHeader><CardTitle className="text-destructive">Errore</CardTitle><CardDescription>Si è verificato un errore imprevisto.</CardDescription></CardHeader>
        <CardContent><div className="p-4 bg-destructive/10 rounded-md"><p className="text-sm text-destructive font-mono">{error}</p></div></CardContent>
        <CardFooter><Button variant="outline" onClick={resetState} className="w-full">Riprova</Button></CardFooter>
      </Card>
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      <fieldset disabled={isProcessing}>
        <Card>
          <CardHeader><CardTitle>1. Caricamento File</CardTitle><CardDescription>Fornisci i 4 file di configurazione in formato .xlsx o .xls.</CardDescription></CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {fileInputConfigs.map(config => <FileUploader key={config.id} {...config} file={files[config.id]} setFile={handleFileChange} disabled={isProcessing} />)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>2. Parametri Algoritmo</CardTitle><CardDescription>Configura i parametri per l'algoritmo genetico.</CardDescription></CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div><Label>Data Inizio</Label><DatePicker date={params.data_inizio} setDate={(d) => handleDateChange('data_inizio', d)} /></div>
              <div><Label>Data Fine</Label><DatePicker date={params.data_fine} setDate={(d) => handleDateChange('data_fine', d)} /></div>
              <div><Label htmlFor="ore_tot_civics">Ore Totali Ed. Civica</Label><Input id="ore_tot_civics" type="number" value={params.ore_tot_civics} onChange={handleParamChange} /></div>
              <div><Label htmlFor="num_generazioni">Numero Generazioni</Label><Input id="num_generazioni" type="number" value={params.num_generazioni} onChange={handleParamChange} /></div>
              <div><Label htmlFor="popolazione_size">Dimensione Popolazione</Label><Input id="popolazione_size" type="number" value={params.popolazione_size} onChange={handleParamChange} /></div>
              <div><Label htmlFor="early_stopping_n">Early Stopping (generazioni)</Label><Input id="early_stopping_n" type="number" value={params.early_stopping_n} onChange={handleParamChange} /></div>
            </div>
            <div className="space-y-4">
              <div><Label>Prob. Mutazione: {params.probabilita_mutazione}</Label><Slider min={0} max={1} step={0.01} value={[params.probabilita_mutazione]} onValueChange={(v) => handleSliderChange('probabilita_mutazione', v)} /></div>
              <div><Label>Prob. Crossover: {params.probabilita_crossover}</Label><Slider min={0} max={1} step={0.01} value={[params.probabilita_crossover]} onValueChange={(v) => handleSliderChange('probabilita_crossover', v)} /></div>
              <div><Label>Tasso Elitismo: {params.elitismo_rate}</Label><Slider min={0} max={0.1} step={0.001} value={[params.elitismo_rate]} onValueChange={(v) => handleSliderChange('elitismo_rate', v)} /></div>
            </div>
            <div className="flex items-center space-x-2"><Checkbox id="allow_teacher_replace_self" checked={params.allow_teacher_replace_self} onCheckedChange={(c) => setParams(p => ({...p, allow_teacher_replace_self:!!c}))} /><Label htmlFor="allow_teacher_replace_self">Consenti a un docente di sostituire se stesso</Label></div>
          </CardContent>
          <CardFooter><Button type="submit" disabled={!isFormValid || isProcessing} className="w-full">{isProcessing ? 'Elaborazione...' : 'Genera Calendario'}</Button></CardFooter>
        </Card>
      </fieldset>
    </form>
  );
}
