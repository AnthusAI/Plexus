'use client';

import { Button as DocButton } from "@/components/ui/button"
import { useTranslationContext } from '@/app/contexts/TranslationContext'
import Link from "next/link"

export default function AdvancedPage() {
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">Herramientas y Conceptos Avanzados</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Explora herramientas y conceptos avanzados que permiten una integración más profunda y personalización de Plexus 
          para usuarios técnicos y desarrolladores.
        </p>

        <div className="space-y-8">
          <section>
            <h2 className="text-2xl font-semibold mb-4">Interfaz de Línea de Comandos</h2>
            <div className="space-y-4">
              <p className="text-muted-foreground mb-4">
                La herramienta CLI <code>plexus</code> proporciona acceso potente por línea de comandos a toda la funcionalidad de Plexus, 
                perfecta para automatización y flujos de trabajo avanzados.
              </p>
              <Link href="/es/documentation/advanced/cli">
                <DocButton>Explorar Herramienta CLI</DocButton>
              </Link>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Infraestructura de Nodos de Trabajo</h2>
            <div className="space-y-4">
              <p className="text-muted-foreground mb-4">
                Aprende cómo configurar y gestionar nodos de trabajo de Plexus para procesar tareas de manera eficiente 
                en tu infraestructura.
              </p>
              <Link href="/es/documentation/advanced/worker-nodes">
                <DocButton>Aprender sobre Nodos de Trabajo</DocButton>
              </Link>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">SDK de Python</h2>
            <div className="space-y-4">
              <p className="text-muted-foreground mb-4">
                Integra Plexus directamente en tus aplicaciones Python con nuestro SDK integral, 
                habilitando acceso programático a todas las características de la plataforma.
              </p>
              <Link href="/es/documentation/advanced/sdk">
                <DocButton>Explorar Referencia SDK</DocButton>
              </Link>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Fragmentos de Código Universal</h2>
            <div className="space-y-4">
              <p className="text-muted-foreground mb-4">
                Aprende sobre el formato de código YAML universal de Plexus diseñado para comunicación perfecta 
                entre humanos, modelos de IA y otros sistemas.
              </p>
              <Link href="/es/documentation/advanced/universal-code">
                <DocButton>Explorar Fragmentos de Código Universal</DocButton>
              </Link>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Servidor MCP de Plexus</h2>
            <div className="space-y-4">
              <p className="text-muted-foreground mb-4">
                Habilita agentes de IA y herramientas para interactuar con la funcionalidad de Plexus usando el Protocolo Cooperativo Multi-Agente (MCP).
              </p>
              <Link href="/es/documentation/advanced/mcp-server">
                <DocButton>Explorar Servidor MCP</DocButton>
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
      <h1 className="text-4xl font-bold mb-4">Advanced Tools & Concepts</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Explore advanced tools and concepts that enable deeper integration and customization of Plexus 
        for technical users and developers.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Command Line Interface</h2>
          <div className="space-y-4">
            <p className="text-muted-foreground mb-4">
              The <code>plexus</code> CLI tool provides powerful command-line access to all Plexus functionality, 
              perfect for automation and advanced workflows.
            </p>
            <Link href="/en/documentation/advanced/cli">
              <DocButton>Explore CLI Tool</DocButton>
            </Link>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Worker Infrastructure</h2>
          <div className="space-y-4">
            <p className="text-muted-foreground mb-4">
              Learn how to set up and manage Plexus worker nodes to process tasks efficiently 
              across your infrastructure.
            </p>
            <Link href="/en/documentation/advanced/worker-nodes">
              <DocButton>Learn About Workers</DocButton>
            </Link>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Python SDK</h2>
          <div className="space-y-4">
            <p className="text-muted-foreground mb-4">
              Integrate Plexus directly into your Python applications with our comprehensive SDK, 
              enabling programmatic access to all platform features.
            </p>
            <Link href="/en/documentation/advanced/sdk">
              <DocButton>Browse SDK Reference</DocButton>
            </Link>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Universal Code Snippets</h2>
          <div className="space-y-4">
            <p className="text-muted-foreground mb-4">
              Learn about Plexus's universal YAML code format designed for seamless communication 
              between humans, AI models, and other systems.
            </p>
            <Link href="/en/documentation/advanced/universal-code">
              <DocButton>Explore Universal Code Snippets</DocButton>
            </Link>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Plexus MCP Server</h2>
          <div className="space-y-4">
            <p className="text-muted-foreground mb-4">
              Enable AI agents and tools to interact with Plexus functionality using the Multi-Agent Cooperative Protocol (MCP).
            </p>
            <Link href="/en/documentation/advanced/mcp-server">
              <DocButton>Explore MCP Server</DocButton>
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
}