# Knowledge Base: Attack_Clasification.ipynb — Contexto y Guía de Integración

> **Nota de autoría**: Este notebook fue creado por Santiago Ríos Guiral, Santiago Taborda
> Echeverri y Brayan David Ramos Caicedo (UdeA). Se entrega **sin modificar respecto al original**
> al estudiante, pero contiene actividades y celdas de código incompletas que el estudiante debe resolver. Esta KB documenta **contexto adicional** para la redacción de la guía
> y la validación; no duplica el contenido del notebook.

---

## Rol en el laboratorio LabP4_4

| Ítem | Valor |
|---|---|
| Archivo | `LabP4_4/Codigo/Attack_Clasification.ipynb` |
| Rol en LabP4_4 | **Ejercicio 1** — introducción guiada a Machine Learning supervisado |
| El estudiante recibe | ✅ Sí — notebook original con scaffolds y celdas pendientes, preparado para Google Colab |
| Prerrequisito | Ninguno (es el primer ejercicio del laboratorio ML) |
| Conecta con | Ejercicio 2 (ML_Pipeline_DT.ipynb) — mismos conceptos ML aplicados a tráfico IoT |
| Lenguaje de instrucción | Inglés |

---

## Dataset: UNSW-NB15

> ⚠️ **IMPORTANTE — Distinción crítica para la guía del laboratorio**:
>
> Este ejercicio usa el dataset **UNSW-NB15**, que es fundamentalmente DIFERENTE al
> dataset usado en los demás ejercicios ML (ML_Pipeline_DT.ipynb).
>
> | Aspecto | Attack_Clasification.ipynb | ML_Pipeline_DT.ipynb |
> |---|---|---|
> | Dataset | **UNSW-NB15** | **UNSW IoT Traffic Traces** |
> | Origen | Laboratorio de ciberseguridad UNSW | Laboratorio de redes IoT UNSW |
> | Tipo de muestra | Un registro = un **flujo de red** | Un registro = un **paquete IP** |
> | # Features | ~47 features por flujo | 3 features por paquete (encabezado) |
> | Etiqueta | Tipo de ataque (DoS, Fuzzers, etc.) | Tipo de dispositivo IoT |
> | Objetivo ML | Detección de intrusiones (IDS) | Clasificación de dispositivos |
> | Licencia | Libre para investigación | MIT-0 |

### Características del dataset UNSW-NB15

- **Generación**: tráfico real + sintético; capturas pcap procesadas a features por flujo
- **Archivo distribuido**: 3 CSVs en Google Drive (ver celdas del notebook)
  - `UNSW_NB15_testing-set.csv`
  - `UNSW_NB15_training-set.csv`
  - `UNSW_NB15_complete-set.csv`
- **Labels de ataque** (10 clases, mapeo numérico para multiclass):

| Código | Categoría | Descripción breve |
|---|---|---|
| 0 | Backdoor | Acceso persistente no autorizado |
| 1 | Analysis | Exploración de puertos/vulnerabilidades |
| 2 | Fuzzers | Envío de datos aleatorios para provocar fallos |
| 3 | Shellcode | Inyección de código de shell |
| 4 | Reconnaissance | Recolección de información de la red |
| 5 | Exploits | Explotación de vulnerabilidades conocidas |
| 6 | DoS | Denegación de servicio |
| 7 | Worms | Malware autopropagante |
| 8 | Generic | Ataques genéricos no clasificados |
| 9 | Normal | Tráfico legítimo |

### Descarga del dataset

Los enlaces originales del dataset dejaron de estar disponibles. Se creó una carpeta propia en Google Drive con los tres archivos CSV y se actualizaron los identificadores en el notebook. Los IDs actuales son:

```python
# IDs de Google Drive actualizados (Attack_Clasification_copy.ipynb)
complete-set: 1ar_NqHPZiYp9Zd7piZcNZkk-JskvWqwz
training-set: 1JA9YzlFWhiqOYg4in1YEsGgyeJQ5qmwt
testing-set:  1aI_sXc3I8XMCmVSqCuEYXEpht_fseA1m
```

> ⚠️ **Nota para el docente**: Verificar periódicamente que los IDs de Drive sigan
> siendo accesibles públicamente. El script de descarga usa cookies (`/tmp/cookies.txt`)
> que pueden fallar en Colab. Alternativa: alojar los CSVs en una carpeta pública de
> Drive y usar `gdown`.

---

## Estructura del notebook y conceptos clave por sección

### Sección introductoria (Cell 1)

El notebook presenta el contexto del problema de clasificación de tráfico de red como
un problema de **Intrusion Detection System (IDS)** usando aprendizaje supervisado.

**Concepto nuevo para el estudiante**: diferencia entre tráfico de red capturado a
nivel de flujo (features estadísticas: duración, bytes, paquetes, flags) vs. tráfico
a nivel de paquete (lo que verán en ML_Pipeline_DT.ipynb).

### EDA — Análisis exploratorio (Cells 6–16)

El estudiante explora libremente el dataset. Los aspectos más relevantes:
- **Desbalanceo**: Normal > Generic > Exploits >> Worms, Shellcode
- **Outliers**: muchas features tienen valores extremos (sbytes, dload, etc.)
- **Features categóricas**: `proto`, `service`, `state` deben eliminarse o codificarse
- **Boxplots recomendados**: `smean`, `sttl`, `dload`, `sloss`, `spkts` entre otros

**Conexión con ML_Pipeline_DT**: el desbalanceo que el estudiante observa aquí
(más tráfico "Normal" que de algunas categorías de ataque) anticipa el mismo fenómeno
en el dataset IoT (clase 4 "Others" = 74.7%), preparándolo para entender por qué
la clase "Audio" desaparece del árbol L3.

### Problema 1: Clasificación binaria normal/ataque (Cells 24–28)

El estudiante implementa:
- Split 70/30 estratificado
- Al menos 2 clasificadores (Decision Tree, KNN)
- Comparación unbalanced vs. balanced (RandomUnderSampler)
- Matriz de confusión para cada variante

**Concepto clave introducido**: el **accuracy paradox** — un modelo que siempre predice
"Normal" puede tener alta accuracy si "Normal" domina los datos.

**Importancia para el resto del laboratorio**: Este concepto es FUNDAMENTAL para interpretar
correctamente el 84.3% de accuracy del árbol DT en ML_Pipeline_DT.ipynb (donde "Others"
domina con 74.7%), y para entender las métricas de recall bajo en clases minoritarias.

### Problema 2: Normal vs. DDoS (Cells 29–32)

Subproblema binario más simple donde el estudiante puede ver cómo aislar
un tipo de ataque específico. Introduce la idea de que diferentes problemas
de clasificación pueden requerir diferentes subsets del dataset.

### Problema 3: Clasificación multiclase (Cells 33–39)

El más cercano al ejercicio siguiente (ML_Pipeline_DT.ipynb) en estructura.
El estudiante enfrenta 10 clases simultáneamente con severo desbalanceo.

Opciones exploradas:
- Unbalanced: alta accuracy en clases grandes, pobre en clases pequeñas
- Balanced: mejor recall en clases pequeñas, posible accuracy global más baja
- Balanced + eliminación de clases con muy pocas muestras (Worms, Shellcode)

### Feature selection y estandarización (Cells 40–42)

El estudiante explora libremente qué features aportan más información.
Esta es la conexión conceptual más directa con la **limitación de 3 features**
en ML_Pipeline_DT.ipynb: mientras que UNSW-NB15 tiene ~47 features de flujo,
P4 solo puede acceder a 3 campos del encabezado del paquete sin estado de flujo.

**Actividades concretas en estas celdas:**
- Cell 41: seleccionar un subconjunto de características numéricas, repetir la
  clasificación binaria con DecisionTree y comparar la exactitud.
- Cell 42: aplicar StandardScaler, repetir la clasificación con DecisionTree y
  KNN, observar que el árbol es invariante a escala mientras que KNN sí se beneficia
  de la estandarización.

---

## Conceptos pedagógicos establecidos para los ejercicios posteriores

Este notebook establece el vocabulario y la intuición ML que el estudiante necesita
para los ejercicios 2–4 del LabP4_4:

| Concepto establecido aquí | Uso en los ejercicios siguientes |
|---|---|
| Accuracy paradox (class imbalance) | Interpretar el 84.3% del árbol DT en ML_Pipeline_DT |
| Accuracy y matriz de confusión | Evaluar los clasificadores implementados por el estudiante y preparar la interpretación del árbol IoT |
| Decision Tree como clasificador | Base para entender DT-in-P4 (Ejercicio 3) |
| Undersampling | Justifica por qué Audio desaparece del árbol L3 |
| Clasificación binaria (normal vs. ataque) | Marco conceptual del ejercicio RL (Ejercicio 4): normal vs. SYN flood |
| Feature selection | Motiva la elección de 3 features en P4 |

---

## Notas técnicas del notebook

### Librerías requeridas

```python
numpy, pandas, statsmodels
matplotlib, seaborn
sklearn (decomposition, pipeline, preprocessing, model_selection, metrics, neighbors, tree, etc.)
```

> El notebook hace `import init; init.init(force_download=False)` desde un repositorio
> externo (`rramosp/2021.deeplearning`). Este init puede instalar paquetes adicionales.
> Verificar que esta URL siga activa antes de cada sesión del laboratorio.

### Entorno recomendado

- **Google Colab** (diseñado explícitamente para este entorno)
- La descarga automática del dataset requiere acceso a internet durante la ejecución
- Tiempo estimado de carga: 2–5 minutos (3 archivos CSV desde Drive)

### Columnas del dataset y preprocesamiento

El notebook elimina consistentemente las columnas categóricas antes del entrenamiento:
```python
df_attack_ub = df_attack.drop(columns=['id','proto','service','state','label'])
```
Esto deja ~43 features numéricas para los clasificadores.

---

## Notas para la redacción de la guía de laboratorio (LabP4_4.tex)

- El notebook incluye código de preparación, pero el estudiante debe implementar:
  - Los boxplots exploratorios (Cell 16)
  - Los clasificadores binarios desbalanceados con árbol de decisión y KNN (Cell 26)
  - Los clasificadores binarios balanceados con RandomUnderSampler (Cell 28)
  - La selección de características y comparación de exactitud (Cell 41)
  - La estandarización y comparación árbol vs. KNN (Cell 42, añadida)
- Las celdas 26 y 28 contienen scaffolds incompletos para clasificación binaria; las secciones DoS y multiclase requieren completar los experimentos; las dos últimas consignas tienen celdas de código vacías.
- Precision, recall y F1 no están solicitadas ni importadas explícitamente por este notebook; pertenecen a la evaluación detallada del notebook ML\_Pipeline\_DT.
- Los puntos de reflexión más importantes que la guía debe reforzar:
  1. ¿Por qué la accuracy alta no siempre significa un buen modelo? (accuracy paradox)
  2. ¿Qué ocurre cuando reducimos el número de features? (prepara para 3-feature DT)
  3. ¿Cómo el desbalanceo de clases afecta la precisión de clases minoritarias?
  4. ¿Por qué la estandarización afecta a KNN pero no al árbol de decisión?
- La guía puede comparar el proceso de este ejercicio con el de ML_Pipeline_DT.ipynb:
  - "En el ejercicio anterior usaron flujos de red con 47 características.
     En este ejercicio usarán paquetes IP con solo 3 características de encabezado.
     ¿Por qué esta limitación? ¿Qué ganamos al tener el clasificador *dentro* del switch?"

---

## Estado del notebook

- ✅ Conservado tal como fue entregado por los autores originales, con actividades pendientes intencionales
- ✅ Descarga automática del dataset en Google Colab
- ⚠️ Verificar periódicamente que los Google Drive IDs de descarga sigan activos
- ⚠️ Verificar que `init.py` del repositorio `rramosp/2021.deeplearning` siga disponible
