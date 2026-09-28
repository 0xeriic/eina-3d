# Eina 3D

Maqueta 3D del Campus Río Ebro (EINA, Universidad de Zaragoza) que te dice cuál es tu próxima clase y te lleva al aula: entrada, escalera o ascensor y planta.

**Web:** https://0xeriic.github.io/eina-3d/

## Tu horario

- **Configurarlo en la web:** elige grado o máster, curso(s), asignaturas y grupos (teoría, problemas y prácticas). La configuración se guarda en tu navegador y puedes descargarla como `.ics`.
- **Subir tu `.ics`:** el que se descarga en la [Consulta pública de horarios de Unizar](https://sia.unizar.es/pds/consultaPublica/look[conpub]InicioPubHora?entradaPublica=true).

Nada de tu horario se envía a ningún servidor.

## Datos

- `data/`: horarios públicos de todos los grados y másteres de la EINA (centro 110), ambos cuatrimestres. Los descarga cada noche `scripts/scrape_sia.py` desde la Consulta pública de horarios (acción «Actualizar horarios» en `.github/workflows/horarios.yml`). Solo se hace commit si algo ha cambiado.
- Planos y datos de espacios: visor IDEUZ (Campus FiDigital, Universidad de Zaragoza).

Proyecto no oficial: comprueba siempre el horario oficial.
