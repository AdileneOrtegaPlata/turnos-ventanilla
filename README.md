# Ventanilla Turnos

Aplicación web de muestra para administrar la fila de atención de una sucursal: emisión de turnos, prioridad, asignación a cuatro ventanillas, control de atención y citas hasta cuatro meses adelante. La interfaz usa una identidad visual bancaria genérica; no está afiliada a BBVA ni utiliza su marca.

## Requisitos

- Python 3.10 o posterior
- Node.js 20.11 o posterior y npm

## Ejecutar en desarrollo

### API Python

En una terminal PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

La API queda en `http://localhost:8000`; Swagger está en `http://localhost:8000/docs`. SQLite crea `backend/turnos.db` al iniciar.

### Interfaz Angular

En otra terminal:

```powershell
cd frontend
npm install
npm start
```

Abre `http://localhost:4200`. La interfaz consulta la API local cada diez segundos.

## Funcionalidad incluida

- Generar turnos con folio diario y tipo de servicio.
- Marcar prioridad preferente; la fila llama primero los turnos preferentes.
- Cuatro ventanillas configurables como activas o pausadas.
- Llamar al siguiente turno, iniciar atención y finalizarla.
- Programar citas hasta cuatro meses adelante; pasan a la fila al llegar su horario.
- Resumen de la operación y lista de turnos del día.
- API documentada automáticamente mediante OpenAPI/Swagger.

## API principal

| Método | Ruta | Acción |
|---|---|---|
| `GET` | `/api/health` | Estado de la API |
| `GET` | `/api/turns` | Turnos del día |
| `POST` | `/api/turns` | Crear turno o cita |
| `GET` | `/api/counters` | Ver estado de ventanillas |
| `POST` | `/api/counters/{id}/next` | Llamar siguiente turno |
| `POST` | `/api/turns/{id}/start` | Iniciar atención |
| `POST` | `/api/turns/{id}/complete` | Finalizar atención |
| `PATCH` | `/api/counters/{id}` | Activar o pausar ventanilla |
| `GET` | `/api/stats` | Resumen diario |

## Preparar subida a GitHub

El proyecto está listo localmente y aún no se ha publicado. Para asociarlo con el repositorio proporcionado, desde la carpeta del proyecto:

```powershell
git init
git add .
git commit -m "Crear sistema de turnos de ventanilla"
git branch -M main
git remote add origin https://github.com/AdileneOrtegaPlata/turnos-ventanilla.git
git push -u origin main
```

Si ese repositorio ya contiene archivos o commits, primero habrá que integrar esa historia antes del primer `push`.

