# CronoSpark

Calendario personal en Flask — listo para desplegar en Render.

## Cómo ejecutar localmente

1. Crear virtualenv e instalar dependencias:

```bash
python -m venv venv
source venv/bin/activate  # o venv\Scripts\activate en Windows
pip install -r requirements.txt
````

2. Crear la BD y correr la app:

```bash
export FLASK_APP=app.py
flask run
# o
python app.py
```

## Despliegue en Render

1. Conecta tu repo a Render.
2. En settings del servicio: Build Command `pip install -r requirements.txt` (Render lo hace automáticamente).
3. Start Command: `gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT` (ya está en Procfile).
4. Si usas PostgreSQL en Render, configura `DATABASE_URL` en las Environment Variables.

¡Listo! La app usará la DB indicada en `DATABASE_URL`, y si no existe, caerá a SQLite local (`cronospark.db`).