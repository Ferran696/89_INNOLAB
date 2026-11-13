# FreezeProof — demo local

**Repositori privat:** [Ferran696/89_INNOLAB](https://github.com/Ferran696/89_INNOLAB)

Prototip de hackató per observar visualment el flux de producte en una línia de congelació i preparar una conversa de servei. La Basler Dart ja muntada a la Raspberry Pi s'utilitza per capturar clips autoritzats; la detecció i el seguiment s'executen després al PC. No cal inferència en directe, servidor ni Hailo.

**Límits:** el recompte és una estimació visual de peces que travessen una línia, no un comptador homologat ni una base de facturació. RGB no mesura pes, geometria real, temperatura interior, innocuïtat ni congelació correcta. La càrrega és un índex de deteccions configurat, no superfície ni capacitat tèrmica.

## Privacitat i dades

- Usa aquesta carpeta per al codi i els exemples neutres. No hi copiïs vídeos originals, anotacions, pesos, telemetria de client ni documents interns.
- `.gitignore` exclou per defecte vídeos, CSV de dades, models i documents d'oficina; només permet el CSV de receptes i la plantilla de telemetria.
- Un repositori privat no és autorització per transferir dades de feina al PC personal, pujar-les a GitHub o carregar-les a Roboflow. Confirma per escrit permisos del client i de l'empresa, ús del PC personal, servei extern, accés i retenció; segueix el canal corporatiu aprovat.
- Per a la primera execució, usa una escena de taula i mantén `clip_origin: simulated`. Canvia-ho a `real` només per a vídeo real autoritzat i sense informació identificable.

## Preparació al PC

Recomanat: Python 3.11 o 3.12 per a la compatibilitat de PyTorch/Ultralytics. El repositori no inclou pesos YOLO: usa un model local autoritzat i revisa'n la llicència abans de qualsevol ús comercial.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Si ja tens un entorn Python aprovat, pots executar les proves de lògica sense instal·lar OpenCV/YOLO:

```powershell
py -m unittest discover -s tests
```

## Flux de demostració

1. Segueix [`capture/README.md`](capture/README.md) i [`docs/capture-checklist.md`](docs/capture-checklist.md) per preparar el clip curt. Si no hi ha permís de planta, grava productes de prova en una escena de taula i etiqueta tot el material com a simulació.
2. Després de transferir el clip per un canal aprovat, processa'l amb pesos locals:

```powershell
.\.venv\Scripts\python -m src.process_video "C:\ruta\aprovada\clip_001.mp4" --model "C:\ruta\local\best.pt" --config config\demo.yaml --output-dir outputs
```

`config/demo.yaml` comença amb `clip_origin: simulated`, una zona i una línia orientatives. Ajusta la zona/línia a cada enquadrament abans de processar cap clip; la direcció `positive` és del costat negatiu al positiu de la línia orientada de l'extrem inicial al final. No modifiquis les seguretats del túnel ni connectis el prototip al PLC.

3. Genera l'informe local sense connexió. El vídeo és opcional i ha de ser el fitxer anotat creat al pas anterior:

```powershell
.\.venv\Scripts\python -m src.build_report --events outputs\events.csv --occupancy outputs\occupancy.csv --video outputs\clip_001_annotated.mp4 --output outputs\report.html
```

Obre `outputs/report.html` localment. La pàgina no carrega recursos d'internet; el vídeo s'enllaça com a fitxer local.

### Telemetria opcional

La plantilla [`config/telemetry-template.csv`](config/telemetry-template.csv) defineix `time_s`, `n2_kg_interval`, `interval_s`, `tunnel_id` i `origin` (`real` o `simulat`). `time_s` és el començament de l'interval; `--telemetry-offset-s` s'hi suma per expressar-lo en el rellotge del clip. L'informe només informa N₂/unitat quan els intervals cobreixen completament el vídeo, són contigus, corresponen a un únic túnel i el vídeo és avaluable. No converteix litres a kg ni presenta una lectura de dipòsit compartit com a consum exacte de línia.

```powershell
.\.venv\Scripts\python -m src.build_report --events outputs\events.csv --occupancy outputs\occupancy.csv --telemetry "C:\ruta\aprovada\telemetry.csv" --telemetry-offset-s 0.0 --output outputs\report.html
```

Si no hi ha mesura sincronitzada, N₂/unitat queda com a no disponible; si el recompte és zero, és no aplicable. La informació simulada queda marcada com a simulació.

### Simulador de preus

Les receptes de 200 g i 500 g són referències declarades manualment; el pes no genera tarifes. Les tarifes del CSV queden pendents fins que s'introdueixin hipòtesis explícites. Aquests imports arbitraris només il·lustren l'ordre del CLI: no són preus proposats ni aprovats; substitueix-los per hipòtesis autoritzades per a la presentació.

```powershell
.\.venv\Scripts\python -m src.pricing --fixed-fee 10 --units burger_200g=100 --rate-eur-per-unit burger_200g=0.12 --units burger_500g=20 --rate-eur-per-unit burger_500g=0.21 --approved-extra "Extra aprovat=5"
```

El resultat es marca `simulated_non_billable` i `invoice_eligible: false`. Les unitats i els imports són entrades explícites, no una liquidació basada automàticament en el vídeo.

## Fitxers principals

```text
capture/README.md
config/demo.yaml
config/recipes.csv
config/telemetry-template.csv
src/process_video.py
src/build_report.py
src/pricing.py
src/counting.py
src/metrics.py
src/reporting.py
tests/
docs/capture-checklist.md
docs/dataset-guidelines.md
docs/service-outline.md
docs/pitch.md
outputs/                  # ignorat per Git; només resultats locals
```

Els clips de validació, els pesos YOLO i qualsevol exemple de reserva s'han de generar i revisar localment després d'obtenir autoritzacions. No hi ha resultats de planta inclosos en aquest repositori.