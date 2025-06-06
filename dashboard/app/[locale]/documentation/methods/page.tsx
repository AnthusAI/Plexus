'use client';

import { Button as DocButton } from "@/components/ui/button"
import { useTranslationContext } from '@/app/contexts/TranslationContext'
import Link from "next/link"

export default function MethodsPage() {
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">Métodos</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Bienvenido a nuestra sección de guías paso a paso. Aquí encontrarás instrucciones detalladas y prácticas para todas las operaciones comunes en Plexus. Ya sea que estés configurando tu primera fuente, creando cuadros de puntuación o ejecutando evaluaciones, estas guías te guiarán a través de cada proceso paso a paso.
        </p>

        <div className="space-y-8">
          <section>
            <h2 className="text-2xl font-semibold mb-4">Gestión de Fuentes</h2>
            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-medium mb-2">Agregar y Editar Fuentes</h3>
                <p className="text-muted-foreground mb-4">
                  Aprende cómo crear nuevas fuentes y gestionar las existentes a través del panel de control.
                </p>
                <Link href="/es/documentation/methods/add-edit-source">
                  <DocButton>Ver Guía de Gestión de Fuentes</DocButton>
                </Link>
              </div>

              <div>
                <h3 className="text-xl font-medium mb-2">Perfilado de Fuentes</h3>
                <p className="text-muted-foreground mb-4">
                  Entiende cómo analizar tus fuentes para obtener insights sobre sus características.
                </p>
                <Link href="/es/documentation/methods/profile-source">
                  <DocButton>Aprender sobre Perfilado</DocButton>
                </Link>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Configuración de Evaluaciones</h2>
            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-medium mb-2">Crear Cuadros de Puntuación</h3>
                <p className="text-muted-foreground mb-4">
                  Configura criterios de evaluación completos con cuadros de puntuación personalizados.
                </p>
                <Link href="/es/documentation/methods/add-edit-scorecard">
                  <DocButton>Explorar Creación de Cuadros</DocButton>
                </Link>
              </div>

              <div>
                <h3 className="text-xl font-medium mb-2">Configurar Puntuaciones</h3>
                <p className="text-muted-foreground mb-4">
                  Define métricas de evaluación individuales y sus parámetros.
                </p>
                <Link href="/es/documentation/methods/add-edit-score">
                  <DocButton>Configurar Ajustes de Puntuación</DocButton>
                </Link>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Ejecutar Evaluaciones</h2>
            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-medium mb-2">Evaluar Contenido</h3>
                <p className="text-muted-foreground mb-4">
                  Procesa tus fuentes usando cuadros de puntuación para generar insights.
                </p>
                <Link href="/es/documentation/methods/evaluate-score">
                  <DocButton>Comenzar a Evaluar Contenido</DocButton>
                </Link>
              </div>

              <div>
                <h3 className="text-xl font-medium mb-2">Gestión de Tareas</h3>
                <p className="text-muted-foreground mb-4">
                  Rastrea y gestiona tareas de evaluación a través de su ciclo de vida.
                </p>
                <Link href="/es/documentation/methods/monitor-tasks">
                  <DocButton>Monitorear tus Tareas</DocButton>
                </Link>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Próximos Pasos</h2>
            <p className="text-muted-foreground mb-4">
              ¿Listo para comenzar? Empieza con la gestión de fuentes para configurar tu contenido para evaluación.
            </p>
            <div className="flex gap-4">
              <Link href="/es/documentation/methods/add-edit-source">
                <DocButton>Comenzar Gestión de Fuentes</DocButton>
              </Link>
              <Link href="/es/documentation/concepts">
                <DocButton variant="outline">Revisar Conceptos Fundamentales</DocButton>
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
      <h1 className="text-4xl font-bold mb-4">Methods</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Welcome to our step-by-step guides section. Here you'll find detailed, practical instructions for all common operations in Plexus. Whether you're setting up your first source, creating scorecards, or running evaluations, these guides will walk you through each process step by step.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Source Management</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Adding and Editing Sources</h3>
              <p className="text-muted-foreground mb-4">
                Learn how to create new sources and manage existing ones through the dashboard.
              </p>
              <Link href="/en/documentation/methods/add-edit-source">
                <DocButton>View Source Management Guide</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Source Profiling</h3>
              <p className="text-muted-foreground mb-4">
                Understand how to analyze your sources to gain insights into their characteristics.
              </p>
              <Link href="/en/documentation/methods/profile-source">
                <DocButton>Learn About Profiling</DocButton>
              </Link>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Evaluation Setup</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Creating Scorecards</h3>
              <p className="text-muted-foreground mb-4">
                Set up comprehensive evaluation criteria with custom scorecards.
              </p>
              <Link href="/en/documentation/methods/add-edit-scorecard">
                <DocButton>Explore Scorecard Creation</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Configuring Scores</h3>
              <p className="text-muted-foreground mb-4">
                Define individual evaluation metrics and their parameters.
              </p>
              <Link href="/en/documentation/methods/add-edit-score">
                <DocButton>Configure Score Settings</DocButton>
              </Link>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Running Evaluations</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Evaluating Content</h3>
              <p className="text-muted-foreground mb-4">
                Process your sources using scorecards to generate insights.
              </p>
              <Link href="/en/documentation/methods/evaluate-score">
                <DocButton>Start Evaluating Content</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Task Management</h3>
              <p className="text-muted-foreground mb-4">
                Track and manage evaluation tasks through their lifecycle.
              </p>
              <Link href="/en/documentation/methods/monitor-tasks">
                <DocButton>Monitor Your Tasks</DocButton>
              </Link>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Next Steps</h2>
          <p className="text-muted-foreground mb-4">
            Ready to get started? Begin with source management to set up your content for evaluation.
          </p>
          <div className="flex gap-4">
            <Link href="/en/documentation/methods/add-edit-source">
              <DocButton>Start Managing Sources</DocButton>
            </Link>
            <Link href="/en/documentation/concepts">
              <DocButton variant="outline">Review Core Concepts</DocButton>
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
} 