# Perché l'orario non si può ottimizzare ulteriormente

Analisi dell'ultima generazione sui dati reali (30 classi, 3 docenti di educazione civica, dal 19/10/2026 al
10/06/2027). Tutti i numeri sono misurati sui file di input e sull'output di quella esecuzione, salvo dove è
scritto "calcolo".

## In sintesi

- La fitness del calendario generato è **692,7**.
- L'**ottimo teorico ignorando le sovrapposizioni tra classi** è **690,1** (somma dei minimi esatti delle singole
  classi, calcolati come se ogni classe avesse i docenti di civica tutti per sé).
- La distanza dall'ottimo teorico è di **1,0 punti nelle unità del modello (691,1 contro 690,1, 0,15%)** e di 2,6
  se la fitness è ricalcolata con `calcola_fitness` (0,4%): è tutto ciò che le sovrapposizioni tra classi
  costano. Anche con infiniti docenti di civica non si scenderebbe sotto 690,1, e il solver ha dimostrato
  l'ottimalità di ogni gruppo di classi entro lo 0,5%.
- I 690,1 non sono una carenza dell'algoritmo: sono imposti dai dati (`classes.csv`, `availability.csv`). Con la
  stessa funzione obiettivo e gli stessi dati non esiste un orario migliore. Cambiare la funzione (provato il
  minimax, vedi sotto) non produce miglioramenti reali.

## Come si calcola l'ottimo teorico

`_minimo_classe` risolve per ogni classe, con una programmazione dinamica esatta, il problema "quali ore perde ogni
docente per coprire le ore di civica richieste", ignorando che gli stessi docenti di civica servono anche altre
classi. Usa gli stessi costi del modello (`_penalita_docente` e varianza), quindi è un limite inferiore valido. Il
solver lo usa già come vincolo.

| Gruppo di classi (un docente di civica) | Classi | Ottimo teorico | Soluzione trovata |
|---|---|---|---|
| 1 | 9 | 325,4 | 326,0 |
| 2 | 10 | 205,9 | 206,3 |
| 3 | 11 | 158,7 | 158,8 |
| **Totale** | **30** | **690,1** | **691,1** (modello) / **692,7** (`calcola_fitness`) |

La soluzione per gruppo è l'obiettivo riportato dal solver. Il modello arrotonda le percentuali ai decimi di
punto, per questo `calcola_fitness` dà 1,6 punti in più sulla stessa soluzione (non verificato nel dettaglio).

## Da cosa è formata la fitness 692,7

| Componente | Valore | Controllabile? |
|---|---|---|
| Penalità piatta per le coppie classe-docente senza ore coperibili | 63,0 | no |
| Varianza delle percentuali (peso 5) | 425,4 | quasi per niente (21,2) |
| Eccesso quadratico oltre la quota proporzionale | 204,2 | solo in parte |

## Perché i dati impongono questo minimo

### 1. Il 14% delle ore di lezione non può mai essere sostituito

Le ore di lezione in totale sono 27.299, distribuite in 263 coppie classe-docente. Il docente di civica può coprire
una lezione solo se in quella cella oraria ha `DISPOS` in `availability.csv`. In **63 coppie su 263** nessuna lezione
cade mai in una cella `DISPOS` del docente di civica della classe: sono **3.893 ore (14,3%)** con zero candidati.
Quei docenti perdono 0 ore per dati, non per scelta del solver.

Conseguenze, tutte non eliminabili:

1. **Penalità piatta di 63 punti**: ogni coppia con perdita sotto lo 0,3 della quota proporzionale prende 1 punto
   (0,5 per gli organici), e le 63 coppie sono tutte lì.
2. **Quasi tutta la varianza (circa 404 su 425)**: la varianza è calcolata su tutti i docenti della classe, compresi
   quelli a 0%. Le coppie a zero restano a zero qualunque cosa faccia il solver, quindi la loro distanza dalla
   media è una costante. Solo 21,2 punti di varianza dipendono da come si distribuisce l'orario.
3. **Un eccesso inevitabile per le coppie che possono perdere ore**: la quota proporzionale è
   `ore_totali × P / 100` con `P = ore di civica della classe / ore di lezione della classe`, dove il denominatore
   include anche le ore dei docenti senza candidati. Le quote sommate dei soli docenti con candidati coprono quindi meno
   delle ore da recuperare, e la differenza ricade per forza su di loro. Misurato: la percentuale di ore perse
   ponderata sulle coppie con candidati è **4,02%** contro un valore proporzionale di **3,45%**, cioè 1,165 volte,
   dove 1,0 sarebbe la quota esatta. Non si può scendere sotto questo rapporto.

### 2. Il caso più sfavorevole: 3BLC e 5BLC

Per ogni classe, il rapporto minimo possibile tra percentuale persa e quota proporzionale è l'inverso della
frazione di ore di lezione che stanno su docenti con candidati (calcolo).

| Classe | Ore su docenti con candidati | Rapporto minimo teorico | Rapporto massimo ottenuto | Ottimo teorico della classe |
|---|---|---|---|---|
| 3BLC | 63% | 1,58 | 1,73 | 71,1 |
| 5BLC | 64% | 1,56 | 1,63 | 64,8 |
| media 30 classi | 86% | 1,18 | 1,30 | 23,0 |

Esempio (calcolo): la 3BLC ha 30 ore di civica da recuperare e solo il 63% delle ore di lezione sono recuperabili.
Quindi circa 30 × (1 − 0,63) ≈ 11 ore sono in eccesso rispetto alla quota proporzionale, qualunque sia la scelta del
solver. Queste due classi valgono 136 dei 690 punti dell'ottimo teorico, quasi il 20%.

### 3. Le ore sono intere

Perdere un'ora in più o in meno cambia la percentuale di un docente di un passo discreto: mediano 1,08 punti
percentuali (fino a 3,45 per i docenti con poche ore). Il rapporto massimo di una classe non può quindi assumere
ogni valore: nei casi peggiori spostare un'ora vale circa 0,14 di rapporto, e il miglioramento possibile è dello
stesso ordine di grandezza dello scarto residuo (0,12 in media tra rapporto massimo ottenuto e quello ideale).

### 4. Il numero di ore per classe è già al massimo

Le settimane utili sono 33 (182 giorni scolastici), quindi 33 ore per classe sarebbero il tetto. Le ore reali sono
**da 30 a 32 per classe (940 totali su 990)**: nelle settimane corte per le chiusure i tre docenti di civica non
hanno abbastanza celle `DISPOS` per coprire tutte le classi insieme. `_assegna_settimane` calcola con un
accoppiamento massimo quante classi si possono coprire in ogni settimana e toglie l'ora a rotazione alle altre.
Questo numero non dipende dalla funzione obiettivo, ma solo dalle disponibilità.

## Cosa è stato provato oltre al minimo teorico

Strategia minimax sul rapporto massimo per classe, con la fitness attuale come criterio secondario. Tutti i gruppi
risolti con ottimo dimostrato (script in una copia temporanea, repo non modificato):

| | Attuale | Minimax |
|---|---|---|
| Fitness | 692,2 | 694,4 |
| Rapporto massimo | 1,727 | 1,687 |
| Rapporto massimo medio per classe | 1,295 | 1,290 |
| Deviazione standard dei rapporti | 0,166 | 0,171 |
| Coppie con rapporto sopra 1,4 | 8 | 9 |

Il caso peggiore migliora di 0,04 e lo stesso risultato esce con peso 100 e con peso 10.000. La media per classe è
praticamente invariata, la dispersione peggiora leggermente: il minimax sposta ore da una coppia all'altra senza
aumentare l'equità. Non conviene adottarlo.

Anche togliere le coppie senza candidati dalla varianza e dalla penalità piatta porterebbe la fitness a circa 225,
ma sarebbe lo stesso orario: sarebbe solo un numero più leggibile.

## Cosa migliorerebbe davvero l'orario

Solo cambiando i dati:

1. **Più celle `DISPOS` in `availability.csv`** per i docenti di civica nelle ore in cui cadono le lezioni oggi non
   coperibili. È la leva più grande: riduce le 63 coppie bloccate, abbassa l'eccesso inevitabile e la varianza, e in
   cima alla lista ci sono 3BLC e 5BLC.
2. **Più docenti di civica** o meno classi per docente: riduce le settimane in cui un'ora manca (oggi 1-3 per classe)
   e il costo delle sovrapposizioni (i 2,6 punti sopra l'ottimo teorico).

Un margine non misurato: la scelta delle settimane senza ora è fissata prima del solver (`_assegna_settimane`) e non
è parte dell'ottimizzazione. Integrarla nel modello potrebbe dare un piccolo guadagno, ma non è stato verificato.
