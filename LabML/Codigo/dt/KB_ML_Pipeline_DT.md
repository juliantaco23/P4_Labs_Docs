# Knowledge Base: ML_Pipeline_DT.ipynb — Pipeline de Machine Learning para Clasificación IoT

## Contexto y rol en el laboratorio

| Item | Valor |
|---|---|
| Archivo | `LabML/Codigo/dt/ML_Pipeline_DT.ipynb` |
| Rol en LabML | Ejercicio 2 — el estudiante observa y ejecuta el pipeline completo |
| El estudiante recibe | ✅ Sí — notebook completo y ejecutable |
| Prerrequisito | Ejercicio 1 (Attack_Clasification.ipynb) — fundamentos de ML supervisado |
| Genera | `tree_L3_generado.txt`, `tree_L4_generado.txt` |
| Salida usada en | Ejercicio 3 (dt_switch.p4) — el estudiante traduce las reglas del árbol a P4 |

---

## Dataset: UNSW IoT Traffic Traces

### Descripción general

| Atributo | Valor |
|---|---|
| Nombre | UNSW IoT Traffic Traces |
| Autores | Sivanathan et al. (2018) |
| Paper | *Classifying IoT devices in smart environments using network traffic characteristics*, IEEE TMC |
| Licencia | **MIT-0** (sin restricciones de uso o distribución) |
| Fuente | https://iotanalytics.unsw.edu.au/iottraces.html |
| Formato distribuido | 20 archivos `.csv.zip` |
| Tamaño comprimido | ~109 MB total (rango: 2.65–16.46 MB por archivo) |
| Tamaño en RAM | ~126 MB (cuando se cargan los 20 días) |
| Total de paquetes IP | 21,061,054 paquetes |
| Período | Septiembre–Octubre 2016 (20 días) |

### Estructura del CSV

Cada fila representa un **paquete IP** capturado en la red doméstica del laboratorio.
Columnas relevantes:

| Columna | Tipo | Uso |
|---|---|---|
| `eth.src` | string (MAC) | Identifica el dispositivo fuente → etiqueta de clase |
| `IP.proto` | float32 | Protocolo de red (6=TCP, 17=UDP, 1=ICMP) |
| `port.src` | float32 | Puerto fuente (TCP o UDP); NaN para ICMP |
| `port.dst` | float32 | Puerto destino (TCP o UDP); NaN para ICMP |

Las columnas restantes del CSV (timestamp, bytes, flags, etc.) **no se usan** en este pipeline.

### Mapeo MAC → clase

Los dispositivos se agrupan en 5 clases según su tipo de IoT:

| Clase | Nombre | # Dispositivos | # Paquetes | % total |
|---|---|---|---|---|
| 0 | Smart-Static (hubs, enchufes) | 8 MACs | 1,145,176 | 5.4% |
| 1 | Sensors (movimiento, clima) | 4 MACs | 282,017 | 1.3% |
| 2 | Audio (altavoces inteligentes) | 4 MACs | 608,165 | 2.9% |
| 3 | Video (cámaras IP, Smart TV) | 9 MACs | 3,288,995 | 15.6% |
| 4 | Others (tráfico no clasificado) | resto | 15,736,701 | 74.7% |

**Desbalanceo de clases**: la clase 4 (Others) representa el 74.7% del dataset.
Esto tiene implicaciones directas en el entrenamiento: el árbol CART optimiza
la impureza de Gini, lo que hace que tienda a maximizar la predicción de la clase
mayoritaria, absorbiendo clases pequeñas como Audio (2.9%) en hojas de Others.

### Protocolo de transporte en el dataset real

El dataset UNSW IoT contiene **casi exclusivamente tráfico TCP y UDP**:
- TCP: ~60–65% de los paquetes
- UDP: ~30–35% de los paquetes  
- ICMP y otros: <5%

Esto explica por qué `ip_proto` **no genera un split** en el árbol L3 ni L4:
el protocolo por sí solo no discrimina bien entre las 5 clases IoT, y el
algoritmo CART no lo selecciona como característica informativa al construir el árbol.

---

## Análisis de viabilidad: distribución del dataset

El notebook actual carga los CSV desde una ruta local relativa:
```python
CSV_DIR = os.path.join('..', '..', 'Legacy', 'iottraces_dataset', 'csv')
```

### Opción A — Subir a Google Drive (RECOMENDADO)

| Criterio | Evaluación |
|---|---|
| Tamaño total | 109 MB — perfectamente viable en Drive (límite: 15 GB gratuito) |
| Acceso desde notebook | Via `gdown` o `wget` con enlace de carpeta pública |
| Compatibilidad con Google Colab | ✅ Total — ideal para ejecución en la nube |
| Complejidad de setup | Baja — el docente sube la carpeta una vez; el estudiante no descarga manualmente |
| Reproducibilidad | Alta — todos los estudiantes usan los mismos archivos |

**Adaptación sugerida en el notebook** (Cell 5, reemplazar la carga local):
```python
import gdown, os, glob

DRIVE_FOLDER_ID = "XXXX_ID_DE_LA_CARPETA_EN_DRIVE"
os.makedirs('csv_data', exist_ok=True)
gdown.download_folder(id=DRIVE_FOLDER_ID, output='csv_data', quiet=False)
CSV_DIR = 'csv_data'
```

### Opción B — GitHub (NO RECOMENDADO para este dataset)

| Criterio | Evaluación |
|---|---|
| Tamaño por archivo | 2.65–16.46 MB — dentro del límite de 100 MB/archivo |
| Tamaño total | 109 MB — dentro del límite técnico, pero inadecuado para datos binarios |
| Política de GitHub | Desaconseja almacenar datasets grandes (recomienda Git LFS) |
| Git LFS | Agrega complejidad innecesaria; tiene límites de banda gratuita |
| Conclusión | ❌ No recomendado — datasets no deben vivir en repos de código |

### Opción C — Descarga directa desde UNSW

| Criterio | Evaluación |
|---|---|
| Disponibilidad | Los archivos están en https://iotanalytics.unsw.edu.au/iottraces.html |
| Descarga programática | No está claro si hay endpoint estable para wget/curl |
| Velocidad | Depende del servidor externo; no apto para lab presencial |
| Conclusión | ⚠️ Solo como fallback; no garantiza disponibilidad continua |

### Opción D — Distribuir localmente (situación actual)

| Criterio | Evaluación |
|---|---|
| Uso | Lab presencial donde el docente distribuye los archivos |
| Configuración | El estudiante extrae el zip en `Legacy/iottraces_dataset/csv/` |
| Ventaja | Sin dependencia de internet durante la sesión |
| Desventaja | Requiere distribución manual (USB, servidor local, etc.) |

**Recomendación final**: Usar Google Drive (Opción A) como canal primario para
entregas remotas o Colab, y mantener la Opción D como respaldo para sesiones presenciales.

---

## Estructura del notebook — sección por sección

| Cell | Sección | Descripción | Estudiante actúa |
|---|---|---|---|
| 1 | Contexto académico | Referencia a IIsy, motivación del ejercicio | Lectura |
| 2 | — | Separador | — |
| 3 | Sec. 0: Imports | Librerías: sklearn, pandas, numpy, matplotlib | Ejecutar |
| 4 | — | Separador | — |
| 5 | Sec. 2: Dataset | Carga 20 CSV.zip; muestra distribución de clases | Ejecutar; observar |
| 6 | — | Separador | — |
| 7 | Sec. 3.1: EDA — Stats | Estadísticas básicas: shape, head, describe | Ejecutar |
| 8 | Sec. 3.2: Feature dist. | Histogramas ip_proto, src_port, dst_port por clase | Ejecutar; analizar |
| 9 | Sec. 3.3: Protocolo | Distribución protocolo por clase (TCP/UDP/ICMP) | Ejecutar |
| 10 | — | Separador | — |
| 11 | Sec. 4: Preprocessing | Split 70/30 estratificado; SEED=42 | Ejecutar |
| 12 | — | Separador | — |
| 13 | Sec. 5.1: depth compare | Tabla comparativa accuracy/leaves para depth 1–6 | Ejecutar; analizar |
| 14 | Sec. 5.2: L3 training | Entrena árbol L3 (max_depth=3) | Ejecutar |
| 15 | — | Separador | — |
| 16 | Sec. 6.1: Visualización | Renderiza el árbol con plot_tree | Ejecutar; interpretar |
| 17 | — | Separador | — |
| 18 | Sec. 7.1: get_lineage | Función de extracción de reglas del árbol | Lectura del código |
| 19 | Sec. 7.2: generar txt | Ejecuta get_lineage; guarda tree_L3_generado.txt | Ejecutar |
| 20 | — | Separador | — |
| 21 | Sec. 8.1: Evaluación | Accuracy, classification report, confusion matrix | Ejecutar; interpretar |
| 22 | Sec. 8.3: L4 tree | Entrena L4 (max_depth=4); genera tree_L4_generado.txt | Ejecutar |
| 23 | Referencias | Citas bibliográficas | Lectura |

---

## Función get_lineage — extracción de reglas del árbol

### Propósito

Convierte el árbol CART interno de sklearn en el formato textual de `tree_L3_generado.txt`:
```
ip_proto = [];
src_port = [547, 1899, 3071, 49280, 60633];
dst_port = [67, 1917];

 when src_port<=547 and dst_port<=67 and src_port<=547 then 1;
 when src_port<=3071 and dst_port<=67 and src_port>547 then 4;
 ...
```

Este formato deriva de `IIsy/iisy_sw/framework/Machinelearning.py` del repositorio
GITA/ONOSP4-tutorial.

### Corrección técnica importante

La versión original de `get_lineage` tenía un bug para árboles con profundidad > 1.
El error era:
```python
# ❌ Bug original — TypeError: only 0-dimensional arrays can be converted to scalars
parent = int(np.where(left == node)[0])  
```

**Fix aplicado** en la Cell 18 de este notebook:
```python
# ✅ Corrección — indexar el elemento escalar con [0][0]
parent = int(np.where(left == node)[0][0])
predicted_class = int(np.argmax(value[leaf][0]))
```

### Salida de get_lineage

El archivo `tree_L3_generado.txt` contiene:
1. **Listas de thresholds por feature** — los nodos de splitting del árbol
2. **Reglas `when...then`** — las rutas desde la raíz hasta cada hoja

Las reglas se leen de izquierda a derecha; la clase `then X` indica la clase de IoT predicha
(0=Smart-Static, 1=Sensors, 2=Audio, 3=Video, 4=Others).

> **Limitación pedagógica (3 features)**: El ejercicio usa solo 3 features del paquete
> (`ip_proto`, `src_port`, `dst_port`) por diseño intencional:
> - Son las únicas features disponibles en el plano de datos (encabezados IP/TCP) sin estado de flujo
> - Permiten implementar el clasificador directamente en P4 con match/action tables de tipo `range`
> - Un modelo con más features requeriría extracción de características de estado (fuera del alcance del laboratorio)

---

## Resultados del entrenamiento (árbol L3, validados)

| Métrica | Valor |
|---|---|
| Training accuracy | 84.27% |
| Test accuracy | 84.27% (sin sobreajuste) |
| Profundidad efectiva | 3 niveles |
| Número de hojas | 8 |
| Número total de nodos | 15 |
| Feature más importante | `src_port` (importancia ≈ 0.78) |
| `ip_proto` importancia | 0.000 (sin split) |

### Reporte de clasificación (test set)

| Clase | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| 0 Smart-Static | 0.39 | 0.92 | 0.55 | 343,553 |
| 1 Sensors | 0.82 | 0.16 | 0.26 | 84,605 |
| 2 Audio | 0.00 | 0.00 | 0.00 | 182,449 |
| 3 Video | 0.72 | 0.80 | 0.76 | 986,699 |
| 4 Others | 0.96 | 0.89 | 0.92 | 4,721,011 |
| **weighted avg** | **0.86** | **0.84** | **0.84** | **6,318,317** |

### Interpretación pedagógica del resultado

1. **Accuracy alta (84%) enmascarada por desbalanceo**: La clase 4 (Others, 74.7%) domina;
   el modelo consigue alta accuracy simplemente prediciendo Others para la mayoría de casos.

2. **Clase 2 (Audio) con F1=0**: El árbol L3 no produce ninguna hoja para Audio.
   Audio (~2.9%) es absorbido por la clase 4 al calcular Gini; a profundidad 3 no hay
   suficiente información discriminante para separar Audio de Others en solo 3 splits.

3. **Smart-Static con recall alto (0.92) pero precision baja (0.39)**: El árbol
   identifica muchos paquetes como Smart-Static (el split `src_port ≤ 3071, dst_port > 1917`)
   pero incluye falsos positivos de otras clases.

4. **Sensors con precision alta (0.82) pero recall bajo (0.16)**: Solo el camino más
   específico (`src_port ≤ 547, dst_port ≤ 67`) captura Sensors correctamente, dejando
   muchos paquetes Sensors sin clasificar correctamente.

---

## Outputs del notebook

### tree_L3_generado.txt

```
ip_proto = [];
src_port = [547, 1899, 3071, 49280, 60633];
dst_port = [67, 1917];

 when src_port<=3071 and dst_port<=67 and src_port<=547 then 1;
 when src_port<=3071 and dst_port<=67 and src_port>547 then 4;
 when src_port<=3071 and dst_port>67 and src_port<=1899 then 4;
 when src_port<=3071 and dst_port>67 and src_port>1899 then 4;
 when src_port>3071 and src_port<=49280 and dst_port<=1917 then 3;
 when src_port>3071 and src_port<=49280 and dst_port>1917 then 0;
 when src_port>3071 and src_port>49280 and src_port<=60633 then 4;
 when src_port>3071 and src_port>49280 and src_port>60633 then 3;
```

### tree_L4_generado.txt

Árbol de profundidad 4, con 15 hojas y 11 thresholds de src_port (vs. 5 en L3) y 3 de dst_port.
Accuracy L4: ligeramente superior a L3, con más granularidad en el rango de src_port medio.

---

## Relación con los otros notebooks

### → Traduction_Functions.ipynb (NO se entrega al estudiante)

`Traduction_Functions.ipynb` carga el mismo dataset, re-entrena el árbol y contiene:
- **Sección 8**: Conversión de thresholds a intervalos de rango `[min, max]`
- **Sección 9**: Generación de comandos `table_add` en formato bash script

Su salida es `rules-extracted.txt` que tiene dos defectos conocidos:
1. Formato bash (`simple_switch_CLI <<< "..."`) en lugar de formato stdin por línea
2. Usa IPs en hex (`0x0a000103`) donde `ipv4_forward` espera MACs de 48 bits

**La tarea del estudiante** es replicar manualmente este proceso de traducción,
dado `tree_L3_generado.txt`, para aprender la conexión entre thresholds ML y
las match/action tables con `range` matching de P4.

### → PCAP_Processing.ipynb (NO se entrega al estudiante)

Documenta el procesamiento de capturas `.pcap` originales a `.csv.zip` usando `tshark`.
Solo referencia interna para el docente; el estudiante recibe los CSV directamente.

---

## Notas para la redacción de la guía de laboratorio (LabML.tex)

- El estudiante ejecuta este notebook de forma guiada; **no hay TODOs de código**
- El docente debe proveer el dataset (Google Drive recomendado)
- Punto de discusión pedagógica: explicar por qué `ip_proto` no discrimina (ver sección de protocolo arriba)
- Punto de discusión pedagógica: explicar el accuracy paradox por desbalanceo de clases
- La salida del notebook (`tree_L3_generado.txt`) es el input para el Ejercicio 3
- Resaltar que las mismas reglas `when...then` se verán codificadas en P4 con `table_add ... range`
