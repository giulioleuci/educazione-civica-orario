import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";

interface Results {
  calendar_csv: string;
  teachersLost_csv: string;
  orario_classi_xlsx: Uint8Array;
  orario_docenti_xlsx: Uint8Array;
  final_fitness: number;
}

interface ResultsDisplayProps {
  results: Results;
  onReset: () => void;
}

const downloadFile = (blob: Blob, fileName: string) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

export function ResultsDisplay({ results, onReset }: ResultsDisplayProps) {

  const handleDownload = (fileName: string, data: string | Uint8Array) => {
    let blob: Blob;
    if (typeof data === 'string') {
      blob = new Blob([data], { type: 'text/csv;charset=utf-8;' });
    } else {
      blob = new Blob([data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    }
    downloadFile(blob, fileName);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-green-500">Generazione Completata!</CardTitle>
        <CardDescription>
          Il calendario è stato generato con successo. Scarica i file di output qui sotto.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="p-4 bg-secondary rounded-md">
          <p className="text-sm font-medium">Fitness Finale della Soluzione: <span className="font-bold text-primary">{results.final_fitness.toFixed(2)}</span></p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Button onClick={() => handleDownload('calendar.csv', results.calendar_csv)}>
            <Download className="mr-2 h-4 w-4" /> Calendario (.csv)
          </Button>
          <Button onClick={() => handleDownload('teachersLost.csv', results.teachersLost_csv)}>
            <Download className="mr-2 h-4 w-4" /> Statistiche Docenti (.csv)
          </Button>
          <Button onClick={() => handleDownload('orario_classi.xlsx', results.orario_classi_xlsx)}>
            <Download className="mr-2 h-4 w-4" /> Orario Classi (.xlsx)
          </Button>
          <Button onClick={() => handleDownload('orario_docenti.xlsx', results.orario_docenti_xlsx)}>
            <Download className="mr-2 h-4 w-4" /> Orario Docenti (.xlsx)
          </Button>
        </div>
      </CardContent>
      <CardFooter>
        <Button variant="outline" onClick={onReset} className="w-full">
            Esegui una Nuova Generazione
        </Button>
      </CardFooter>
    </Card>
  );
}
