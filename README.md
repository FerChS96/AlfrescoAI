# AlfrescoAI
Consulta de documentos y archivos usando los endpoints de Alfresco Community Edition

# AlfrescoAI 🤖📄

Consulta de documentos y archivos usando los endpoints de Alfresco Community Edition con inteligencia artificial.

## 📋 Descripción

AlfrescoAI es una herramienta que permite realizar consultas inteligentes sobre documentos y archivos almacenados en Alfresco Community Edition, utilizando tecnologías de IA para facilitar la búsqueda y análisis de contenido.

## 🚀 Características

- ✅ Integración con Alfresco Community Edition
- 🔍 Búsqueda inteligente de documentos
- 📊 Análisis de contenido con IA
- 🔗 Conexión mediante API REST
- 📱 Interfaz fácil de usar

## 🛠️ Tecnologías

- **Python 3.x**
- **Alfresco Community Edition**
- **API REST**
- **Librerías de IA/ML**

## 📦 Instalación

1. Clona este repositorio:
```bash
git clone https://github.com/FerChS96/AlfrescoAI.git
cd AlfrescoAI
```

2. Instala las dependencias:
```bash
pip install -r requirements.txt
```

3. Configura las variables de entorno:
```bash
cp .env.example .env
# Edita el archivo .env con tu configuración de Alfresco
```

## ⚙️ Configuración

Crea un archivo `.env` con las siguientes variables:

```env
ALFRESCO_URL=http://localhost:8080/alfresco
ALFRESCO_USERNAME=admin
ALFRESCO_PASSWORD=admin
API_VERSION=v1
```

## 🎯 Uso

### Ejemplo básico

```python
from alfrescoai import AlfrescoAI

# Inicializar cliente
client = AlfrescoAI(
    url="http://localhost:8080/alfresco",
    username="admin",
    password="admin"
)

# Buscar documentos
resultados = client.buscar_documentos("factura 2024")

# Analizar contenido
analisis = client.analizar_documento(documento_id)
```

### Consultas avanzadas

```python
# Búsqueda por tipo de archivo
pdfs = client.buscar_por_tipo("pdf")

# Búsqueda por fecha
documentos_recientes = client.buscar_por_fecha("2024-01-01", "2024-12-31")

# Análisis de sentimientos
sentimiento = client.analizar_sentimiento(documento_id)
```

## 📂 Estructura del Proyecto

```
AlfrescoAI/
├── src/
│   ├── alfrescoai/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── search.py
│   │   └── analysis.py
│   └── examples/
├── tests/
├── docs/
├── requirements.txt
├── .env.example
└── README.md
```

## 🧪 Pruebas

Ejecuta las pruebas unitarias:

```bash
python -m pytest tests/
```

## 📖 Documentación

Para más información, consulta la [documentación completa](docs/).

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-caracteristica`)
3. Commit tus cambios (`git commit -am 'Agrega nueva característica'`)
4. Push a la rama (`git push origin feature/nueva-caracteristica`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.

## 👨‍💻 Autor

**FerChS96** - [GitHub](https://github.com/FerChS96)