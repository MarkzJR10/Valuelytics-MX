# Valuelytics MX ⚽🇲🇽

**Valuelytics MX** es un scanner modular, ligero e ilimitado escrito en Python 3.10+ diseñado para detectar discrepancias de valor matemático (+EV) entre cuotas de casas de apuestas recreativas en México y enviarlas en tiempo real a Telegram.

---

## 🚀 Características Principal

- **Scanner Ilimitado & Gratuito:** Consume endpoints backend JSON directos sin necesidad de depurar navegadores pesados ni pagar APIs de terceros.
- **Motor Matemático Quant:** Retiro de *vig* (margen de la casa) mediante proporcionalidad implícita y cálculo exacto de Valor Esperado (+EV).
- **Integración con Playdoit (Altenar):** Extracción automatizada de eventos top y mercados de 2 opciones (*Total Goals*, *Both Teams to Score*).
- **Alertas en Tiempo Real:** Notificaciones instantáneas enviadas a un canal/bot de Telegram con formato HTML elegante.
- **Mapeo y Normalización:** Limpieza de nombres de equipos y coincidencia difusa (*fuzzy matching* con `thefuzz`).

---

## 📁 Estructura del Proyecto

```
valuelytics-mx/
│
├── config/
│   ├── __init__.py
│   └── settings.py          # Carga de variables desde .env usando python-dotenv
│
├── scrapers/
│   ├── __init__.py
│   ├── base.py              # Clase abstracta BaseScraper con tipado estricto
│   └── playdoit.py          # Scraper JSON de Altenar (GetTopEvents, GetEventDetails)
│
├── core/
│   ├── __init__.py
│   ├── normalizer.py        # Limpieza y fuzzy matching de nombres de equipos
│   └── value_engine.py      # Retiro de vig y cálculo de +EV matemático
│
├── alerts/
│   ├── __init__.py
│   └── telegram_bot.py      # Despacho asíncrono/síncrono de alertas con formato HTML
│
├── tests/
│   ├── test_telegram.py     # Script simple para probar conexión al canal
│   └── test_playdoit.py     # Script para validar lectura de cuotas de Altenar
│
├── main.py                  # Loop principal con scheduler y manejo de excepciones
├── requirements.txt         # Dependencias del proyecto
├── .env.example             # Plantilla de variables de entorno
└── README.md
```

---

## 🛠️ Instalación y Configuración

1. **Clonar / Ubicarse en el repositorio:**
   ```bash
   cd Valuelytics-MX
   ```

2. **Crear y activar un entorno virtual (recomendado):**
   ```bash
   python -m venv venv
   # En Windows:
   venv\Scripts\activate
   # En Linux/Mac:
   source venv/bin/activate
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar el archivo `.env`:**
   Copia la plantilla de ejemplo y edita tus credenciales de Telegram:
   ```bash
   cp .env.example .env
   ```
   Edita `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=tu_token_aqui
   TELEGRAM_CHAT_ID=tu_chat_id_aqui
   MIN_EV_THRESHOLD=0.04
   POLL_INTERVAL_SECONDS=180
   SPORT_ID=66
   ```

---

## 🧪 Pruebas de Funcionamiento

- **Probar el Scraper de Playdoit:**
  ```bash
  python tests/test_playdoit.py
  ```
- **Probar el Bot de Telegram:**
  ```bash
  python tests/test_telegram.py
  ```

---

## 🏃 Ejecución del Scanner

Para iniciar el bot en modo escaneo continuo:

```bash
python main.py
```
