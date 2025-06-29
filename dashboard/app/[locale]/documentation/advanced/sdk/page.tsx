'use client';

import { useTranslationContext } from '@/app/contexts/TranslationContext'

export default function SdkPage() {
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">Referencia del SDK de Python</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Explora el SDK de Python para acceso programático a la funcionalidad de Plexus.
        </p>

        <div className="space-y-8">
          <section>
            <h2 className="text-2xl font-semibold mb-4">Resumen</h2>
            <p className="text-muted-foreground mb-4">
              El SDK de Python de Plexus proporciona una forma simple e intuitiva de interactuar con Plexus
              programáticamente. Úsalo para automatizar flujos de trabajo, gestionar recursos, e integrar
              Plexus en tus aplicaciones.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Instalación</h2>
            <p className="text-muted-foreground mb-4">
              Instala el SDK de Plexus usando pip:
            </p>
            <pre className="bg-muted p-4 rounded-lg mb-4">
              <code>pip install plexus-sdk</code>
            </pre>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Inicio Rápido</h2>
            <p className="text-muted-foreground mb-4">
              Aquí tienes un ejemplo simple para comenzar:
            </p>
            <pre className="bg-muted p-4 rounded-lg mb-4">
              <code>{`from plexus import Plexus

# Inicializar el cliente
plexus = Plexus(api_key="tu-api-key")

# Crear una nueva fuente
source = plexus.sources.create(
    name="Mi Fuente",
    type="text",
    data="Contenido de ejemplo"
)

# Ejecutar una evaluación
evaluation = plexus.evaluations.create(
    source_id=source.id,
    scorecard_id="tu-scorecard-id"
)`}</code>
            </pre>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Documentación Completa</h2>
            <p className="text-muted-foreground mb-4">
              Para la referencia completa de la API, guías de autenticación, ejemplos de uso avanzado y mejores prácticas, 
              visita nuestra documentación integral del SDK de Python:
            </p>
            <div className="mt-4">
              <a 
                href="https://anthusai.github.io/Plexus/" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="inline-flex items-center px-4 py-2 bg-primary text-primary-foreground hover:bg-primary/90 rounded-md transition-colors"
              >
                Ver Documentación Completa del SDK →
              </a>
            </div>
          </section>
        </div>
      </div>
    );
  }
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Python SDK Reference</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Explore the Python SDK for programmatic access to Plexus functionality.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Overview</h2>
          <p className="text-muted-foreground mb-4">
            The Plexus Python SDK provides a simple and intuitive way to interact with Plexus
            programmatically. Use it to automate workflows, manage resources, and integrate
            Plexus into your applications.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Installation</h2>
          <p className="text-muted-foreground mb-4">
            Install the Plexus SDK using pip:
          </p>
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>pip install plexus-sdk</code>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Quick Start</h2>
          <p className="text-muted-foreground mb-4">
            Here's a simple example to get you started:
          </p>
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`from plexus import Plexus

# Initialize the client
plexus = Plexus(api_key="your-api-key")

# Create a new source
source = plexus.sources.create(
    name="My Source",
    type="text",
    data="Sample content"
)

# Run an evaluation
evaluation = plexus.evaluations.create(
    source_id=source.id,
    scorecard_id="your-scorecard-id"
)`}</code>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Complete Documentation</h2>
          <p className="text-muted-foreground mb-4">
            For complete API reference, authentication guides, advanced usage examples, and best practices, 
            visit our comprehensive Python SDK documentation:
          </p>
          <div className="mt-4">
            <a 
              href="https://anthusai.github.io/Plexus/" 
              target="_blank" 
              rel="noopener noreferrer" 
              className="inline-flex items-center px-4 py-2 bg-primary text-primary-foreground hover:bg-primary/90 rounded-md transition-colors"
            >
              View Full SDK Documentation →
            </a>
          </div>
        </section>
      </div>
    </div>
  )
} 