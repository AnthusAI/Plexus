'use client';

import { Button as DocButton } from "@/components/ui/button"
import { useTranslations, useTranslationContext } from '@/app/contexts/TranslationContext'
import Link from "next/link"

export default function DocumentationPage() {
  const t = useTranslations('documentation');
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">Documentación</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Bienvenido a la documentación de Plexus. Aquí encontrarás guías completas y documentación
          para ayudarte a comenzar a trabajar con Plexus lo más rápido posible.
        </p>

        <div className="space-y-8">
          <section>
            <h2 className="text-2xl font-semibold mb-4">Primeros Pasos</h2>
            <div className="grid gap-6 sm:grid-cols-2">
              <div>
                <h3 className="text-xl font-medium mb-2">Conceptos Fundamentales</h3>
                <p className="text-muted-foreground mb-4">
                  Aprende sobre los conceptos y componentes fundamentales que impulsan Plexus.
                </p>
                <Link href="/es/documentation/concepts">
                  <DocButton>Explorar Fundamentos</DocButton>
                </Link>
              </div>

              <div>
                <h3 className="text-xl font-medium mb-2">Guías Paso a Paso</h3>
                <p className="text-muted-foreground mb-4">
                  Sigue guías detalladas para operaciones y flujos de trabajo comunes.
                </p>
                <Link href="/es/documentation/methods">
                  <DocButton>Ver Métodos</DocButton>
                </Link>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Componentes de la Plataforma</h2>
            <div className="grid gap-6 sm:grid-cols-2">
              <div>
                <h3 className="text-xl font-medium mb-2">Nodos de Trabajo</h3>
                <p className="text-muted-foreground mb-4">
                  Configura y gestiona nodos de trabajo para procesar tu contenido a escala.
                </p>
                <Link href="/es/documentation/advanced/worker-nodes">
                  <DocButton>Aprender sobre Workers</DocButton>
                </Link>
              </div>

              <div>
                <h3 className="text-xl font-medium mb-2">
                  Herramienta CLI <code className="text-lg">plexus</code>
                </h3>
                <p className="text-muted-foreground mb-4">
                  Utiliza la interfaz de línea de comandos para gestionar tu implementación de Plexus.
                </p>
                <Link href="/es/documentation/advanced/cli">
                  <DocButton>Explorar CLI</DocButton>
                </Link>
              </div>

              <div>
                <h3 className="text-xl font-medium mb-2">SDK de Python</h3>
                <p className="text-muted-foreground mb-4">
                  Integra Plexus en tus aplicaciones Python de manera programática.
                </p>
                <Link href="/es/documentation/advanced/sdk">
                  <DocButton>Explorar Referencia SDK</DocButton>
                </Link>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Inicio Rápido</h2>
            <p className="text-muted-foreground mb-6">
              La forma más rápida de comenzar con Plexus es:
            </p>
            <ol className="list-decimal pl-6 space-y-4 text-muted-foreground">
              <li>
                <strong className="text-foreground">Revisar los Fundamentos</strong>
                <p>Comprende los conceptos básicos que conforman Plexus.</p>
              </li>
              <li>
                <strong className="text-foreground">Crear tu Primera Fuente</strong>
                <p>Agrega contenido para analizar usando el panel de control.</p>
              </li>
              <li>
                <strong className="text-foreground">Configurar un Cuadro de Puntuación</strong>
                <p>Define cómo quieres evaluar tu contenido.</p>
              </li>
              <li>
                <strong className="text-foreground">Ejecutar una Evaluación</strong>
                <p>Procesa tu contenido y visualiza los resultados.</p>
              </li>
            </ol>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Próximos Pasos</h2>
            <p className="text-muted-foreground mb-4">
              ¿Listo para comenzar? Empieza con los fundamentos para entender los conceptos básicos de Plexus.
            </p>
            <div className="flex gap-4">
              <Link href="/es/documentation/concepts">
                <DocButton>Comenzar con Fundamentos</DocButton>
              </Link>
              <Link href="/es/documentation/methods/add-edit-source">
                <DocButton variant="outline">Ir a Creación de Fuentes</DocButton>
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
      <h1 className="text-4xl font-bold mb-4">Documentation</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Welcome to the Plexus documentation. Here you'll find comprehensive guides and documentation
        to help you start working with Plexus as quickly as possible.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Getting Started</h2>
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="text-xl font-medium mb-2">Core Concepts</h3>
              <p className="text-muted-foreground mb-4">
                Learn about the fundamental concepts and components that power Plexus.
              </p>
              <Link href="/en/documentation/concepts">
                <DocButton>Explore Basics</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Step-by-Step Guides</h3>
              <p className="text-muted-foreground mb-4">
                Follow detailed guides for common operations and workflows.
              </p>
              <Link href="/en/documentation/methods">
                <DocButton>View Methods</DocButton>
              </Link>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Platform Components</h2>
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="text-xl font-medium mb-2">Worker Nodes</h3>
              <p className="text-muted-foreground mb-4">
                Set up and manage worker nodes to process your content at scale.
              </p>
              <Link href="/en/documentation/advanced/worker-nodes">
                <DocButton>Learn About Workers</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">
                <code className="text-lg">plexus</code> CLI Tool
              </h3>
              <p className="text-muted-foreground mb-4">
                Use the command-line interface to manage your Plexus deployment.
              </p>
              <Link href="/en/documentation/advanced/cli">
                <DocButton>Explore CLI</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Python SDK</h3>
              <p className="text-muted-foreground mb-4">
                Integrate Plexus into your Python applications programmatically.
              </p>
              <Link href="/en/documentation/advanced/sdk">
                <DocButton>Browse SDK Reference</DocButton>
              </Link>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Quick Start</h2>
          <p className="text-muted-foreground mb-6">
            The fastest way to get started with Plexus is to:
          </p>
          <ol className="list-decimal pl-6 space-y-4 text-muted-foreground">
            <li>
              <strong className="text-foreground">Review the Basics</strong>
              <p>Understand the core concepts that make up Plexus.</p>
            </li>
            <li>
              <strong className="text-foreground">Create Your First Source</strong>
              <p>Add some content to analyze using the dashboard.</p>
            </li>
            <li>
              <strong className="text-foreground">Set Up a Scorecard</strong>
              <p>Define how you want to evaluate your content.</p>
            </li>
            <li>
              <strong className="text-foreground">Run an Evaluation</strong>
              <p>Process your content and view the results.</p>
            </li>
          </ol>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Next Steps</h2>
          <p className="text-muted-foreground mb-4">
            Ready to get started? Begin with the basics to understand Plexus's core concepts.
          </p>
          <div className="flex gap-4">
            <Link href="/en/documentation/concepts">
              <DocButton>Start with Basics</DocButton>
            </Link>
            <Link href="/en/documentation/methods/add-edit-source">
              <DocButton variant="outline">Jump to Source Creation</DocButton>
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
} 