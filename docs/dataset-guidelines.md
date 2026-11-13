# Preparació i separació de dades

Aquestes pautes serveixen per preparar un conjunt petit després d'obtenir totes les autoritzacions. No hi ha vídeos, anotacions ni dades de client inclosos en aquest repositori.

## Abast i etiquetatge

- Comença amb una línia, una família i una sola referència visible. No barregis hamburgueses i gelats en el mateix entrenament inicial.
- Tria una classe per al producte objectiu i mantén la mateixa convenció d'etiquetatge. Anota el producte sencer amb una caixa ajustada; no facis servir etiquetes per inferir pes, gruix, temperatura ni qualitat de congelació.
- Comença amb aproximadament 100–200 fotogrames diversos. Inclou canvis d'il·luminació, productes propers, parades i variacions reals de la vista, sempre que siguin autoritzats i llegibles.
- No seleccionis només fotogrames consecutius: prioritza moments diferents i errors observats. Fotogrames amb oclusió greu o sense criteri clar s'han de marcar com a difícils/no avaluables segons l'eina, no convertir-los en exemples de cinta buida.
- Si s'utilitza Roboflow, cal aprovació prèvia del client i de l'empresa, revisió de la configuració de privacitat/retenció i confirmació que el compte i l'ús són permesos. Altrament, usa una eina local aprovada.

## Separació d'entrenament i validació

- Assigna els clips o sessions complets a un únic grup abans d'extreure fotogrames: entrenament i validació no poden compartir clip ni sessió.
- Reserva almenys tres clips complets per a validació final; no els miris per ajustar llindars o entrenar el model. Si no hi ha prou clips, informa que la validació és preliminar en lloc de barrejar fotogrames veïns.
- Mantén un registre neutre de `clip_id`, sessió, grup (`train`/`validation`), origen (`real`/`simulat`) i condicions. No hi incloguis noms de clients, persones, productes confidencials ni credencials.
- Per a una escena de taula, identifica tots els fitxers derivats com a **SIMULACIÓ**; no barregis aquestes imatges amb captures reals sense conservar-ne la procedència.

El recompte manual i les anotacions temporals dels clips de validació s'han de conservar separats de les dades d'entrenament. L'objectiu inicial de demo (error total ≤5 % en clips favorables) no és una garantia industrial ni un criteri de facturació.