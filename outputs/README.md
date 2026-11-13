# Outputs locals

Els vídeos anotats i els CSV generats es desen aquí durant l'execució. Aquesta carpeta està exclosa del control de versions per defecte: no hi copiïs vídeos originals, dades de client, anotacions ni pesos del model. La sortida és només una demostració i no és apta per a facturació.

`quality=visually_empty` vol dir que el detector no ha trobat cap objecte a la zona durant un interval d'imatge avaluable; no demostra que la cinta estigui físicament buida. `quality=unevaluable` no contribueix al càlcul de buits ni de càrrega.