'use client';

import { Button as DocButton } from "@/components/ui/button"
import { useTranslationContext } from '@/app/contexts/TranslationContext'
import Link from "next/link"

export default function BasicsPage() {
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">Conceptos Fundamentales</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Aprende sobre los bloques fundamentales que conforman Plexus.
        </p>

        <div className="space-y-8">
          <section>
            <h2 className="text-2xl font-semibold mb-4">Conceptos Principales</h2>
            <div className="grid gap-6 sm:grid-cols-2">
              <div>
                <h3 className="text-xl font-medium mb-2">Items</h3>
                <p className="text-muted-foreground mb-4">
                  Piezas individuales de contenido que deseas analizar o evaluar usando Plexus. Los items son las unidades centrales que se califican.
                </p>
                <Link href="/es/documentation/concepts/items">
                  <DocButton>Aprender sobre Items</DocButton>
                </Link>
              </div>

              <div>
                <h3 className="text-xl font-medium mb-2">Fuentes</h3>
                <p className="text-muted-foreground mb-4">
                  Datos de entrada para evaluación, incluyendo contenido de texto y audio. Las fuentes son la base
                  del análisis de contenido en Plexus.
                </p>
                <Link href="/es/documentation/concepts/sources">
                  <DocButton>Aprender sobre Fuentes</DocButton>
                </Link>
              </div>

              <div>
                <h3 className="text-xl font-medium mb-2">Puntuaciones</h3>
                <p className="text-muted-foreground mb-4">
                  Criterios de evaluación individuales que definen qué medir. Las puntuaciones son los bloques de construcción
                  de los cuadros y pueden variar desde preguntas simples hasta métricas complejas.
                </p>
                <Link href="/es/documentation/concepts/scores">
                  <DocButton>Aprender sobre Puntuaciones</DocButton>
                </Link>
              </div>

              <div>
                <h3 className="text-xl font-medium mb-2">Cuadros de Puntuación</h3>
                <p className="text-muted-foreground mb-4">
                  Colecciones de puntuaciones que forman un marco de evaluación completo. Los cuadros organizan
                  criterios de evaluación relacionados en grupos significativos.
                </p>
                <Link href="/es/documentation/concepts/scorecards">
                  <DocButton>Aprender sobre Cuadros</DocButton>
                </Link>
              </div>

              <div>
                <h3 className="text-xl font-medium mb-2">Evaluaciones</h3>
                <p className="text-muted-foreground mb-4">
                  El proceso de analizar fuentes usando cuadros de puntuación para generar insights
                  y métricas de calidad.
                </p>
                <Link href="/es/documentation/concepts/evaluations">
                  <DocButton>Entender Evaluaciones</DocButton>
                </Link>
              </div>

              <div>
                <h3 className="text-xl font-medium mb-2">Tareas</h3>
                <p className="text-muted-foreground mb-4">
                  Unidades individuales de trabajo en Plexus, representando operaciones como procesamiento de fuentes
                  y evaluaciones.
                </p>
                <Link href="/es/documentation/concepts/tasks">
                  <DocButton>Descubrir Tareas</DocButton>
                </Link>
              </div>

              <div>
                <h3 className="text-xl font-medium mb-2">Reportes</h3>
                <p className="text-muted-foreground mb-4">
                  Análisis y resúmenes flexibles basados en plantillas generados a partir de tus datos de Plexus usando componentes reutilizables.
                </p>
                <Link href="/es/documentation/concepts/reports">
                  <DocButton>Aprender sobre Reportes</DocButton>
                </Link>
              </div>

              <div>
                <h3 className="text-xl font-medium mb-2">Métricas de Evaluación</h3>
                <p className="text-muted-foreground mb-4">
                  Herramientas de visualización especializadas que ayudan a interpretar métricas de acuerdo y precisión, especialmente al manejar datos desbalanceados.
                </p>
                <Link href="/es/documentation/evaluation-metrics">
                  <DocButton>Entender Métricas de Evaluación</DocButton>
                </Link>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Cómo Funciona Todo Junto</h2>
            <p className="text-muted-foreground mb-6">
              El flujo de trabajo de Plexus sigue un patrón simple:
            </p>
            <ol className="list-decimal pl-6 space-y-4 text-muted-foreground">
              <li>
                <strong className="text-foreground">Crear Fuentes</strong>
                <p>Sube o conecta tu contenido para análisis.</p>
              </li>
              <li>
                <strong className="text-foreground">Definir Cuadros de Puntuación</strong>
                <p>Configura criterios de evaluación y reglas de puntuación.</p>
              </li>
              <li>
                <strong className="text-foreground">Ejecutar Evaluaciones</strong>
                <p>Procesa fuentes usando tus cuadros de puntuación.</p>
              </li>
              <li>
                <strong className="text-foreground">Monitorear Tareas y Ver Reportes</strong>
                <p>Rastrea el progreso de evaluaciones y generación de reportes, luego revisa los resultados y reportes generados.</p>
              </li>
            </ol>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Próximos Pasos</h2>
            <p className="text-muted-foreground mb-4">
              Comienza con Fuentes para aprender cómo agregar contenido a Plexus, luego explora Cuadros de Puntuación
              para entender cómo evaluar tu contenido de manera efectiva.
            </p>
            <div className="flex gap-4">
              <Link href="/es/documentation/concepts/sources">
                <DocButton>Comenzar con Fuentes</DocButton>
              </Link>
              <Link href="/es/documentation/methods">
                <DocButton variant="outline">Ver Guías Paso a Paso</DocButton>
              </Link>
            </div>
          </section>
        </div>
      </div>
    );
  }

  // English content (default)
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Core Concepts</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn about the fundamental building blocks that make up Plexus.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Core Concepts</h2>
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="text-xl font-medium mb-2">Items</h3>
              <p className="text-muted-foreground mb-4">
                Individual pieces of content that you want to analyze or evaluate using Plexus. Items are the core units that get scored.
              </p>
              <Link href="/en/documentation/concepts/items">
                <DocButton>Learn about Items</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Sources</h3>
              <p className="text-muted-foreground mb-4">
                Input data for evaluation, including text and audio content. Sources are the foundation
                of content analysis in Plexus.
              </p>
              <Link href="/en/documentation/concepts/sources">
                <DocButton>Learn about Sources</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Scores</h3>
              <p className="text-muted-foreground mb-4">
                Individual evaluation criteria that define what to measure. Scores are the building blocks
                of scorecards and can range from simple questions to complex metrics.
              </p>
              <Link href="/en/documentation/concepts/scores">
                <DocButton>Learn about Scores</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Scorecards</h3>
              <p className="text-muted-foreground mb-4">
                Collections of scores that form a complete evaluation framework. Scorecards organize
                related evaluation criteria into meaningful groups.
              </p>
              <Link href="/en/documentation/concepts/scorecards">
                <DocButton>Learn about Scorecards</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Evaluations</h3>
              <p className="text-muted-foreground mb-4">
                The process of analyzing sources using scorecards to generate insights
                and quality metrics.
              </p>
              <Link href="/en/documentation/concepts/evaluations">
                <DocButton>Understand Evaluations</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Tasks</h3>
              <p className="text-muted-foreground mb-4">
                Individual units of work in Plexus, representing operations like source processing
                and evaluations.
              </p>
              <Link href="/en/documentation/concepts/tasks">
                <DocButton>Discover Tasks</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Reports</h3>
              <p className="text-muted-foreground mb-4">
                Flexible, template-driven analyses and summaries generated from your Plexus data using reusable components.
              </p>
              <Link href="/en/documentation/concepts/reports">
                <DocButton>Learn about Reports</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Evaluation Metrics</h3>
              <p className="text-muted-foreground mb-4">
                Specialized visualization tools that help interpret agreement and accuracy metrics, especially when dealing with imbalanced data.
              </p>
              <Link href="/en/documentation/evaluation-metrics">
                <DocButton>Understand Evaluation Metrics</DocButton>
              </Link>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">How It All Works Together</h2>
          <p className="text-muted-foreground mb-6">
            The Plexus workflow follows a simple pattern:
          </p>
          <ol className="list-decimal pl-6 space-y-4 text-muted-foreground">
            <li>
              <strong className="text-foreground">Create Sources</strong>
              <p>Upload or connect your content for analysis.</p>
            </li>
            <li>
              <strong className="text-foreground">Define Scorecards</strong>
              <p>Set up evaluation criteria and scoring rules.</p>
            </li>
            <li>
              <strong className="text-foreground">Run Evaluations</strong>
              <p>Process sources using your scorecards.</p>
            </li>
            <li>
              <strong className="text-foreground">Monitor Tasks & View Reports</strong>
              <p>Track progress of evaluations and report generation, then review the results and generated reports.</p>
            </li>
          </ol>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Next Steps</h2>
          <p className="text-muted-foreground mb-4">
            Start with Sources to learn how to add content to Plexus, then explore Scorecards
            to understand how to evaluate your content effectively.
          </p>
          <div className="flex gap-4">
            <Link href="/en/documentation/concepts/sources">
              <DocButton>Get Started with Sources</DocButton>
            </Link>
            <Link href="/en/documentation/methods">
              <DocButton variant="outline">View Step-by-Step Guides</DocButton>
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
} 