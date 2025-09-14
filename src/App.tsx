import { Toaster } from "@/components/ui/sonner";
import { GenerationForm } from "@/components/GenerationForm";

function App() {
  return (
    <div className="min-h-screen bg-background font-sans antialiased">
      <div className="container mx-auto p-4 sm:p-6 lg:p-8">
        <header className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-center">
            Generatore Orario Educazione Civica
          </h1>
          <p className="text-muted-foreground text-center mt-2">
            Carica i file di configurazione, imposta i parametri e genera il calendario ottimizzato.
          </p>
        </header>
        <main>
          <GenerationForm />
        </main>
        <Toaster />
      </div>
    </div>
  );
}

export default App;
