'use client';

import { useTranslationContext } from '@/app/contexts/TranslationContext'

export default function ItemsPage() {
  const { locale } = useTranslationContext();

  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">Items</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Aprende sobre los Items, las unidades de contenido principales que Plexus analiza y califica.
        </p>

        <div className="space-y-8">
          <section>
            <h2 className="text-2xl font-semibold mb-4">¿Qué son los Items?</h2>
            <p className="text-muted-foreground mb-4">
              Los Items son piezas individuales de contenido que deseas analizar o evaluar usando Plexus.
              Pueden ser cualquier tipo de contenido que tus técnicas de puntuación de IA, ML o lógicas puedan procesar, como:
            </p>
            <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
              <li>Transcripciones de call center para aseguramiento de calidad</li>
              <li>Correos electrónicos de clientes o tickets de soporte</li>
              <li>Archivos de casos o documentos</li>
              <li>Repositorios de código para análisis</li>
              <li>Imágenes o videos para moderación de contenido</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Cómo Funcionan los Items</h2>
            <p className="text-muted-foreground mb-4">
              Los Items son la base del sistema de evaluación de Plexus:
            </p>
            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-medium mb-2">1. Organización</h3>
                <p className="text-muted-foreground">
                  Cada Elemento pertenece a una Cuenta y puede ser referenciado por múltiples Cuadros de Puntuación.
                  Esto te permite evaluar el mismo contenido usando diferentes criterios o métodos de puntuación.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-medium mb-2">2. Puntuación</h3>
                <p className="text-muted-foreground">
                  Cuando aplicas un Cuadro de Puntuación a un Elemento, Plexus crea un Trabajo de Puntuación para procesarlo.
                  Los resultados se almacenan como Resultados de Puntuación, que contienen las puntuaciones, niveles de confianza
                  y cualquier metadato adicional del proceso de puntuación.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-medium mb-2">3. Evaluación</h3>
                <p className="text-muted-foreground">
                  Los Items pueden ser parte de Evaluaciones, donde sus resultados de puntuación se comparan contra
                  respuestas correctas conocidas para medir la precisión y efectividad de tus métodos de puntuación.
                </p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Propiedades del Item</h2>
            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-medium mb-2">Propiedades Principales</h3>
                <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                  <li><strong>Nombre</strong>: Un identificador único para el Item</li>
                  <li><strong>Descripción</strong>: Detalles opcionales sobre el contenido o propósito del Item</li>
                  <li><strong>Cuenta</strong>: La Cuenta que posee este Item</li>
                </ul>
              </div>
              <div>
                <h3 className="text-xl font-medium mb-2">Relaciones</h3>
                <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                  <li><strong>Cuadros de Puntuación</strong>: Cuadros de Puntuación que referencian este Item</li>
                  <li><strong>Trabajos de Puntuación</strong>: Registros de operaciones de puntuación realizadas en este Item</li>
                  <li><strong>Resultados de Puntuación</strong>: Resultados de operaciones de puntuación</li>
                  <li><strong>Evaluación</strong>: Enlace opcional a una Evaluación de la que este Item forma parte</li>
                </ul>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Mejores Prácticas</h2>
            <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
              <li>Usa nombres claros y descriptivos para tus Items para hacerlos fáciles de identificar</li>
              <li>Incluye metadatos relevantes en la descripción para proporcionar contexto</li>
              <li>Organiza los Items lógicamente dentro de tu estructura de Cuenta</li>
              <li>Mantén un registro de qué Items se usan en Evaluaciones para control de calidad</li>
              <li>Revisa regularmente los Resultados de Puntuación para monitorear la efectividad de la puntuación</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Próximos Pasos</h2>
            <p className="text-muted-foreground mb-4">
              Ahora que entiendes los Items, puedes:
            </p>
            <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
              <li>Crear Cuadros de Puntuación para evaluar tus Items</li>
              <li>Configurar criterios de puntuación usando Puntuaciones</li>
              <li>Ejecutar Evaluaciones para medir la precisión de la puntuación</li>
              <li>Monitorear resultados a través del panel de control</li>
            </ul>
          </section>
        </div>
      </div>
    );
  }

  // English content (default)
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Items</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn about Items, the core content units that Plexus analyzes and scores.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">What are Items?</h2>
          <p className="text-muted-foreground mb-4">
            Items are individual pieces of content that you want to analyze or evaluate using Plexus.
            They can be any type of content that your AI, ML, or logical scoring techniques can process, such as:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>Call center transcripts for quality assurance</li>
            <li>Customer emails or support tickets</li>
            <li>Case files or documents</li>
            <li>Code repositories for analysis</li>
            <li>Images or videos for content moderation</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">How Items Work</h2>
          <p className="text-muted-foreground mb-4">
            Items are the foundation of Plexus's evaluation system:
          </p>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">1. Organization</h3>
              <p className="text-muted-foreground">
                Each Item belongs to an Account and can be referenced by multiple Scorecards.
                This allows you to evaluate the same content using different criteria or scoring methods.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">2. Scoring</h3>
              <p className="text-muted-foreground">
                When you apply a Scorecard to an Item, Plexus creates a ScoringJob to process it.
                The results are stored as ScoreResults, which contain the scores, confidence levels,
                and any additional metadata from the scoring process.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">3. Evaluation</h3>
              <p className="text-muted-foreground">
                Items can be part of Evaluations, where their scoring results are compared against
                known correct answers to measure the accuracy and effectiveness of your scoring methods.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Item Properties</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Core Properties</h3>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li><strong>Name</strong>: A unique identifier for the Item</li>
                <li><strong>Description</strong>: Optional details about the Item's content or purpose</li>
                <li><strong>Account</strong>: The Account that owns this Item</li>
              </ul>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Relationships</h3>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li><strong>Scorecards</strong>: Scorecards that reference this Item</li>
                <li><strong>ScoringJobs</strong>: Records of scoring operations performed on this Item</li>
                <li><strong>ScoreResults</strong>: Results from scoring operations</li>
                <li><strong>Evaluation</strong>: Optional link to an Evaluation this Item is part of</li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Best Practices</h2>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>Use clear, descriptive names for your Items to make them easy to identify</li>
            <li>Include relevant metadata in the description to provide context</li>
            <li>Organize Items logically within your Account structure</li>
            <li>Keep track of which Items are used in Evaluations for quality control</li>
            <li>Regularly review ScoreResults to monitor scoring effectiveness</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Next Steps</h2>
          <p className="text-muted-foreground mb-4">
            Now that you understand Items, you can:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>Create Scorecards to evaluate your Items</li>
            <li>Set up scoring criteria using Scores</li>
            <li>Run Evaluations to measure scoring accuracy</li>
            <li>Monitor results through the dashboard</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 