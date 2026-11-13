# Captura amb Basler Dart i Raspberry Pi 5

Aquesta guia prepara clips curts per a una demo local. La Basler ja està muntada a la Pi; no s'ha de modificar el túnel, el PLC, les proteccions ni el procés de producció.

## Abans d'engegar

- Confirma per escrit l'autorització del client i de l'empresa per gravar, conservar els vídeos i tractar-los fora de planta. L'ús d'un PC personal o d'un servei extern requereix aprovació explícita; un repositori privat no la substitueix.
- Identifica el model de càmera, objectiu, versió de l'SDK i configuració que ja funciona. Aquesta guia no pressuposa un model de lent, SDK o format concret.
- Fixa la càmera de manera estable, preferiblement zenital i abans del túnel, fora de la zona freda i sense envair espais de pas ni interferir amb higiene, accessos, proteccions o operació.
- Il·lumina la cinta de manera estable i difusa. Evita reflexos, ombres mòbils, parpelleig i llum que pugui molestar operadors. No moguis ni ajustis equips de planta sense autorització.
- Enquadra només la zona necessària. No incloguis persones, pantalles, etiquetes, documents, receptes identificables ni altres dades del client.

## Configuració de captura

1. Utilitza l'eina o el programa Basler que ja estigui configurat a la Pi. No instal·lis ni actualitzis SDKs a planta sense autorització de l'equip responsable.
2. Deixa la càmera fixa durant cada clip. Comprova l'enfocament i l'exposició amb la cinta en moviment i amb producte; si no es poden ajustar de forma segura, atura la prova i demana suport.
3. Escull una resolució i una freqüència de fotogrames que permetin distingir peces i seguir-ne el moviment, sense perdre fotogrames. Mantén aquests paràmetres iguals entre clips sempre que sigui possible.
4. Desa els originals en una ubicació local aprovada, amb noms neutres (`clip_001`, `clip_002`, ...). Registra per separat la data/sessió, els paràmetres de captura i si l'escena és real o simulada; no posis noms de client ni de producte als noms dels fitxers.
5. Si l'eina existent ho permet, prefereix un vídeo amb temps i freqüència reproduïbles i compatible amb l'ordinador que farà l'anàlisi. No converteixis ni esborris l'original fins que hagis comprovat la còpia i la reproducció al PC.

## Clip curt de comprovació

Abans de capturar el conjunt complet, grava un clip de 20–30 segons amb el format que s'utilitzarà després. Reprodueix-lo al PC de processament i verifica:

- que el fitxer s'obre, dura el temps esperat i no té talls ni fotogrames corruptes;
- que les vores de les peces són llegibles, sense desenfocament de moviment o saturació;
- que la cinta i la zona de recompte romanen dins del camp de visió;
- que no hi apareixen persones, pantalles ni informació identificable;
- que la freqüència i la resolució observades són suficients per distingir peces properes i aturades.

Si una comprovació falla, no continuïs amb la captura completa: corregeix-ho només amb autorització i torna a fer el clip curt. No s'ha verificat físicament aquest muntatge des d'aquest repositori; aquesta comprovació s'ha de fer amb la Pi i la càmera reals.

## Clips objectiu

Quan hi hagi permisos i una escena segura, prepara inicialment 6–10 clips de 20–60 segons: càrrega regular, intervals visualment buits, peces properes/juntes i una parada o reinici observables. Evita provocar aturades o alterar el procés; grava només esdeveniments normals o coordinats amb Operacions. Una escena de taula amb productes de prova és una alternativa vàlida si l'accés a planta no està autoritzat.

Els clips originals i els pesos del model han de quedar fora dels lliurables públics. No els carreguis a Roboflow ni a GitHub sense aprovació específica de l'empresa i del client, i sense revisar la política de retenció i privacitat.