'use client';

import { MessageSquareCode } from 'lucide-react';
import { CodeSnippet } from '@/components/ui/code-snippet';
import FeedbackAnalysis from '@/components/blocks/FeedbackAnalysis';
import { useTranslationContext } from '@/app/contexts/TranslationContext'

export default function YAMLCodeStandardPage() {
  const { locale } = useTranslationContext();
  // Create the YAML data but also parse it into the object structure for the component
  const sampleYAMLCode = `# Sales Lead Routing Analysis Report Output
# 
# This is the structured output from a sales lead routing analysis process that:
# 1. Retrieves lead routing decisions from scorecards within a specified time range
# 2. Analyzes agreement between initial and final routing decisions using Gwet's AC1 coefficient
# 3. Provides statistical measures of inter-rater reliability and agreement
# 4. Generates insights about routing quality and consistency across sales operations teams
#
# The output contains agreement scores, statistical measures, detailed breakdowns,
# and analytical insights for understanding lead routing consistency and reliability.

overall_ac1: 0.912
total_items: 28470
total_mismatches: 2505
total_agreements: 25965
accuracy: 91.2
total_feedback_items_retrieved: 28470
date_range:
  start: "2024-07-15T00:00:00"
  end: "2024-07-21T23:59:59"
message: "Processed 3 score(s)."
classes_count: 2
label_distribution:
  "Yes": 15259
  "No": 13211
confusion_matrix:
  labels: ["Yes", "No"]
  matrix:
    - actualClassLabel: "Yes"
      predictedClassCounts:
        "Yes": 14096
        "No": 1163
    - actualClassLabel: "No"
      predictedClassCounts:
        "Yes": 1342
        "No": 11869
class_distribution:
  - label: "Yes"
    count: 15259
  - label: "No"
    count: 13211
predicted_class_distribution:
  - label: "Yes"
    count: 15438
  - label: "No"
    count: 13032
precision: 91.3
recall: 92.4
warning: null
warnings: null
notes: null
discussion: null
block_title: "Sales Lead Routing Analysis"
block_description: "Inter-rater Reliability Assessment"

scores:
  - score_id: "55123"
    score_name: "Lead properly categorized by product type"
    cc_question_id: "2001"
    ac1: 0.962
    item_count: 9847
    mismatches: 374
    agreements: 9473
    accuracy: 96.2
    classes_count: 2
    label_distribution:
      "Yes": 6574
      "No": 3273
    confusion_matrix:
      labels: ["Yes", "No"]
      matrix:
        - actualClassLabel: "Yes"
          predictedClassCounts:
            "Yes": 6324
            "No": 250
        - actualClassLabel: "No"
          predictedClassCounts:
            "Yes": 124
            "No": 3149
    class_distribution:
      - label: "Yes"
        count: 6574
      - label: "No" 
        count: 3273
    predicted_class_distribution:
      - label: "Yes"
        count: 6448
      - label: "No"
        count: 3399
    precision: 98.1
    recall: 96.2
    warning: null
    warnings: null
    notes: null
    discussion: null
    indexed_items_file: "lead_routing_analysis_55123_items.json"
    
  - score_id: "55124"
    score_name: "Lead routed to appropriate sales team"
    cc_question_id: "2002"
    ac1: 0.889
    item_count: 10156
    mismatches: 1127
    agreements: 9029
    accuracy: 88.9
    classes_count: 2
    label_distribution:
      "Yes": 5078
      "No": 5078
    confusion_matrix:
      labels: ["Yes", "No"]
      matrix:
        - actualClassLabel: "Yes"
          predictedClassCounts:
            "Yes": 4514
            "No": 564
        - actualClassLabel: "No"
          predictedClassCounts:
            "Yes": 563
            "No": 4515
    class_distribution:
      - label: "Yes"
        count: 5078
      - label: "No"
        count: 5078
    predicted_class_distribution:
      - label: "Yes"
        count: 5077
      - label: "No"
        count: 5079
    precision: 88.9
    recall: 88.9
    warning: null
    warnings: null
    notes: null
    discussion: null
    indexed_items_file: "lead_routing_analysis_55124_items.json"
    
  - score_id: "55125"
    score_name: "Lead priority level correctly assessed"
    cc_question_id: "2003"
    ac1: 0.854
    item_count: 8467
    mismatches: 1004
    agreements: 7463
    accuracy: 85.4
    classes_count: 2
    label_distribution:
      "Yes": 3607
      "No": 4860
    confusion_matrix:
      labels: ["Yes", "No"]
      matrix:
        - actualClassLabel: "Yes"
          predictedClassCounts:
            "Yes": 3155
            "No": 452
        - actualClassLabel: "No"
          predictedClassCounts:
            "Yes": 552
            "No": 4308
    class_distribution:
      - label: "Yes"
        count: 3607
      - label: "No"
        count: 4860
    predicted_class_distribution:
      - label: "Yes"
        count: 3707
      - label: "No"
        count: 4760
    precision: 85.1
    recall: 87.5
    warning: null
    warnings: null
    notes: null
    discussion: "The lead priority assessment shows strong inter-rater reliability with 85.4% agreement between reviewers. This indicates well-defined priority criteria and consistent training across sales operations teams. Minor disagreements primarily occur at priority boundary cases, which is expected. The system demonstrates effective lead qualification processes that support optimal sales team allocation."
    indexed_items_file: "lead_routing_analysis_55125_items.json"`;


  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <div className="mb-6">
          <h1 className="text-4xl font-bold">Fragmentos de Código Universal</h1>
          <p className="text-lg text-muted-foreground">
            Interfaz de código universal para humanos, modelos de IA y sistemas
          </p>
        </div>

        <div className="space-y-8">
          <section className="relative">
            <h2 className="text-2xl font-semibold mb-4">El Icono de Código Universal</h2>
            <div className="absolute top-0 right-0">
              <MessageSquareCode className="h-16 w-16 md:h-20 md:w-20 lg:h-24 lg:w-24 text-primary/20" />
            </div>
            <div className="space-y-4 pr-20 md:pr-24 lg:pr-28">
              <p className="text-muted-foreground">
                En todo Plexus, este icono significa que puedes obtener datos estructurados que funcionan en cualquier lugar. Haz clic, copia la salida, 
                y pégala directamente en ChatGPT, Claude, tu editor de código, o compártela con otros miembros del equipo. 
                El formato YAML incluye contexto integrado para que cualquiera (humano o IA) entienda inmediatamente lo que está viendo.
              </p>
              <p className="text-muted-foreground">
                No más luchar con JSON denso o perder contexto cuando mueves datos entre herramientas. 
                Simplemente funciona, en cualquier lugar.
              </p>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Reporte Visual → Código Universal</h2>
            <p className="text-muted-foreground mb-6">
              Así es como funciona: cada reporte gráfico en Plexus tiene una representación de código correspondiente. 
              A continuación hay un análisis real de enrutamiento de leads de ventas. El reporte visual muestra puntuaciones de acuerdo, matrices de confusión e insights de manera hermosa. 
              El botón de Código revela los mismos datos como YAML contextual que funciona en cualquier lugar.
            </p>

            <div className="p-4 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mb-6">
              <h3 className="text-lg font-semibold mb-2">Prueba el Botón de Código</h3>
              <p className="text-muted-foreground">
                Usa el botón de Código en la esquina superior derecha para ver cómo los insights visuales se transforman en YAML estructurado que funciona con cualquier herramienta de IA, sistema de documentación o repositorio de código.
              </p>
            </div>

            <div>
              <div className="flex justify-end mb-2">
                <div className="flex flex-col items-center">
                  <div className="text-sm text-muted-foreground font-medium mb-1">Código Universal</div>
                  <div className="text-muted-foreground text-3xl font-black animate-attention-bounce">↓</div>
                </div>
              </div>
              <div className="rounded-lg p-4 bg-muted universal-code-demo">
                <FeedbackAnalysis
                  config={{}}
                  output={sampleYAMLCode as any}
                  position={1}
                  type="FeedbackAnalysis"
                  id="sales-lead-routing-example"
                  name="Análisis de Calidad de Enrutamiento de Leads de Ventas"
                  className="border-0 p-0"
                />
              </div>
            </div>

            <div className="bg-muted/30 p-4 rounded-lg mt-6">
              <p className="text-sm text-muted-foreground">
                💡 <strong>Prueba esto:</strong> Usa el botón de Código para revelar YAML contextual con comentarios explicativos. 
                Haz clic en el botón Copiar para copiar el código a tu portapapeles. 
                Pégalo en ChatGPT o Claude y pregunta: "¿Qué puntuaciones de enrutamiento de leads de ventas muestran el mayor desacuerdo entre revisores?" o "¿Qué recomendaciones de entrenamiento mejorarían la confiabilidad del enrutamiento de leads?" 
                La IA entenderá inmediatamente el contexto y te dará recomendaciones estratégicas.
              </p>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Disponible en Todas Partes</h2>
            <p className="text-muted-foreground mb-6">
              Cada bloque de reporte en Plexus genera automáticamente Fragmentos de Código Universal. Ya sea que estés trabajando con 
              análisis de temas, análisis de retroalimentación, matrices de confusión, o cualquier otra salida analítica, el distintivo 
              icono de código te da acceso instantáneo a datos estructurados y contextuales.
            </p>
            
            <p className="text-muted-foreground mb-6">
              También encontrarás Fragmentos de Código Universal en:
            </p>
            
            <div className="grid md:grid-cols-2 gap-4">
              <div className="p-4 bg-card rounded-lg border">
                <h3 className="font-medium mb-2">📊 Bloques de Reporte</h3>
                <p className="text-sm text-muted-foreground">
                  Cada salida analítica incluye el Icono de Código Universal para acceso instantáneo a datos
                </p>
              </div>
              <div className="p-4 bg-card rounded-lg border">
                <h3 className="font-medium mb-2">🎯 Evaluaciones</h3>
                <p className="text-sm text-muted-foreground">
                  Resultados de evaluación con matrices de confusión, métricas de precisión y datos de rendimiento
                </p>
              </div>
              <div className="p-4 bg-card rounded-lg border">
                <h3 className="font-medium mb-2">📈 Analíticas</h3>
                <p className="text-sm text-muted-foreground">
                  Análisis estadístico, puntuaciones de acuerdo e insights de rendimiento
                </p>
              </div>
              <div className="p-4 bg-card rounded-lg border">
                <h3 className="font-medium mb-2">🔧 Configuraciones</h3>
                <p className="text-sm text-muted-foreground">
                  Configuraciones de cuadros de puntuación y puntuaciones exportadas en formato universal
                </p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Por Qué Esto Importa</h2>
            <p className="text-muted-foreground mb-4">
              Las exportaciones de datos tradicionales carecen de contexto cuando las mueves. 
              Los Fragmentos de Código Universal resuelven esto empaquetando tus datos con explicaciones integradas que viajan con ellos.
            </p>
            <p className="text-muted-foreground">
              Esto significa que puedes mover insights sin problemas entre Plexus, tus herramientas de IA, documentación, repositorios de código, 
              y conversaciones de equipo sin perder significado o requerir explicación adicional.
            </p>
          </section>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto py-8 px-6">

      
      <div className="mb-6">
        <h1 className="text-4xl font-bold">Universal Code Snippets</h1>
        <p className="text-lg text-muted-foreground">
          Universal code interface for humans, AI models, and systems
        </p>
      </div>

      <div className="space-y-8">
        <section className="relative">
          <h2 className="text-2xl font-semibold mb-4">The Universal Code Icon</h2>
          {/* Oversized icon positioned at top-right of this section */}
          <div className="absolute top-0 right-0">
            <MessageSquareCode className="h-16 w-16 md:h-20 md:w-20 lg:h-24 lg:w-24 text-primary/20" />
          </div>
          <div className="space-y-4 pr-20 md:pr-24 lg:pr-28">
            <p className="text-muted-foreground">
              Throughout Plexus, this icon means you can grab structured data that works everywhere. Click it, copy the output, 
              and paste it directly into ChatGPT, Claude, your code editor, or share it with other team members. 
              The YAML format includes built-in context so anyone (human or AI) immediately understands what they're looking at.
            </p>
            <p className="text-muted-foreground">
              No more wrestling with dense JSON or losing context when you move data between tools. 
              It just works, everywhere.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Visual Report → Universal Code</h2>
          <p className="text-muted-foreground mb-6">
            Here's how it works: every graphical report in Plexus has a corresponding code representation. 
            Below is a real sales lead routing analysis report. The visual report displays agreement scores, confusion matrices, and insights beautifully. 
            The Code button reveals the same data as contextual YAML that works everywhere.
          </p>

          <div className="p-4 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mb-6">
            <h3 className="text-lg font-semibold mb-2">Try the Code Button</h3>
            <p className="text-muted-foreground">
              Use the Code button in the top-right to see how visual insights transform into structured YAML that works with any AI tool, documentation system, or code repository.
            </p>
          </div>

          <div>
            <div className="flex justify-end mb-2">
              <div className="flex flex-col items-center">
                <div className="text-sm text-muted-foreground font-medium mb-1">Universal Code</div>
                <div className="text-muted-foreground text-3xl font-black animate-attention-bounce">↓</div>
              </div>
            </div>
            <div className="rounded-lg p-4 bg-muted universal-code-demo">
              <FeedbackAnalysis
                config={{}}
                output={sampleYAMLCode as any}
                position={1}
                type="FeedbackAnalysis"
                id="sales-lead-routing-example"
                name="Sales Lead Routing Quality Analysis"
                className="border-0 p-0"
              />
            </div>
          </div>

          <div className="bg-muted/30 p-4 rounded-lg mt-6">
            <p className="text-sm text-muted-foreground">
              💡 <strong>Try this:</strong> Use the Code button to reveal contextual YAML with explanatory comments. 
              Click the Copy button to copy the code to your clipboard. 
              Paste it into ChatGPT or Claude and ask: "Which sales lead routing scores show the highest disagreement between reviewers?" or "What training recommendations would improve lead routing reliability?" 
              The AI will immediately understand the context and give you strategic recommendations.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Available Everywhere</h2>
          <p className="text-muted-foreground mb-6">
            Every report block in Plexus automatically generates Universal Code Snippets. Whether you're working with 
            topic analysis, feedback analysis, confusion matrices, or any other analytical output, the distinctive 
            code icon gives you instant access to structured, contextual data.
          </p>
          
          <p className="text-muted-foreground mb-6">
            You'll also find Universal Code Snippets in:
          </p>
          
          <div className="grid md:grid-cols-2 gap-4">
            <div className="p-4 bg-card rounded-lg border">
              <h3 className="font-medium mb-2">📊 Report Blocks</h3>
              <p className="text-sm text-muted-foreground">
                Every analytical output includes the Universal Code Icon for instant data access
              </p>
            </div>
            <div className="p-4 bg-card rounded-lg border">
              <h3 className="font-medium mb-2">🎯 Evaluations</h3>
              <p className="text-sm text-muted-foreground">
                Evaluation results with confusion matrices, accuracy metrics, and performance data
              </p>
            </div>
            <div className="p-4 bg-card rounded-lg border">
              <h3 className="font-medium mb-2">📈 Analytics</h3>
              <p className="text-sm text-muted-foreground">
                Statistical analysis, agreement scores, and performance insights
              </p>
            </div>
            <div className="p-4 bg-card rounded-lg border">
              <h3 className="font-medium mb-2">🔧 Configurations</h3>
              <p className="text-sm text-muted-foreground">
                Scorecard and score configurations exported in universal format
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Why This Matters</h2>
          <p className="text-muted-foreground mb-4">
            Traditional data exports lack context when you move them around. 
            Universal Code Snippets solve this by packaging your data with built-in explanations that travel with it.
          </p>
          <p className="text-muted-foreground">
            This means you can seamlessly move insights between Plexus, your AI tools, documentation, code repositories, 
            and team conversations without losing meaning or requiring additional explanation.
          </p>
        </section>
      </div>
    </div>
  );
}