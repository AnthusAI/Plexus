'use client';

import { useTranslationContext } from '@/app/contexts/TranslationContext'

export default function ProfileSourcePage() {
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">Perfilar una Fuente</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Aprende cómo analizar y perfilar tus fuentes usando la interfaz del panel de control de Plexus.
        </p>

        <div className="space-y-8">
          <section>
            <h2 className="text-2xl font-semibold mb-4">Perfilado de Fuentes en el Panel de Control</h2>
            <p className="text-muted-foreground mb-4">
              El perfilado de fuentes te ayuda a entender las características y patrones en tus datos
              antes de ejecutar evaluaciones. El panel de control proporciona herramientas completas para analizar
              tus fuentes.
            </p>
            
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-medium mb-3">Guía Paso a Paso</h3>
                <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                  <li>
                    <strong>Acceder a Detalles de Fuente:</strong>
                    <p>Navega a tu fuente en la lista de Fuentes y haz clic en ella para ver detalles.</p>
                  </li>
                  <li>
                    <strong>Iniciar Perfilado:</strong>
                    <p>Haz clic en el botón "Perfilar Fuente" en la vista de detalles de la fuente.</p>
                  </li>
                  <li>
                    <strong>Configurar Análisis:</strong>
                    <p>Selecciona las opciones de perfilado que deseas ejecutar:</p>
                    <ul className="list-disc pl-6 mt-2 space-y-2">
                      <li>Análisis de contenido</li>
                      <li>Detección de patrones</li>
                      <li>Métricas de calidad</li>
                      <li>Opciones de análisis personalizado</li>
                    </ul>
                  </li>
                  <li>
                    <strong>Ejecutar Perfil:</strong>
                    <p>Haz clic en "Iniciar Análisis" para comenzar el proceso de perfilado.</p>
                  </li>
                  <li>
                    <strong>Revisar Resultados:</strong>
                    <p>Una vez completo, examina los resultados detallados del perfilado en el panel de control.</p>
                  </li>
                </ol>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Entendiendo los Resultados del Perfil</h2>
            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-medium mb-2">Análisis de Contenido</h3>
                <p className="text-muted-foreground">
                  Ve desgloses detallados del contenido de tu fuente, incluyendo estructura, formato
                  y características clave. El panel de control presenta esta información a través de
                  visualizaciones interactivas y reportes detallados.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-medium mb-2">Detección de Patrones</h3>
                <p className="text-muted-foreground">
                  Explora patrones identificados y anomalías a través de la vista de análisis de patrones
                  del panel de control. Esto te ayuda a entender temas comunes y problemas potenciales
                  en tu contenido.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-medium mb-2">Métricas de Calidad</h3>
                <p className="text-muted-foreground">
                  Revisa mediciones de calidad completas a través de gráficos intuitivos y
                  desgloses detallados de métricas en la interfaz del panel de control.
                </p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Consejos de Gestión de Perfiles</h2>
            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-medium mb-2">Guardar Perfiles</h3>
                <p className="text-muted-foreground">
                  Guarda configuraciones de perfil como plantillas para reutilización rápida en múltiples fuentes.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-medium mb-2">Comparar Resultados</h3>
                <p className="text-muted-foreground">
                  Usa la vista de comparación del panel de control para analizar resultados de perfil entre diferentes
                  fuentes o períodos de tiempo.
                </p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Usar la CLI</h2>
            <p className="text-muted-foreground mb-4">
              Para flujos de trabajo automatizados de perfilado, puedes usar la CLI de Plexus:
            </p>
            
            <pre className="bg-muted p-4 rounded-lg mb-4">
              <code>{`# Ejecutar un perfil en una fuente
plexus sources profile source-id --analysis-type full

# Obtener resultados del perfil
plexus sources profile-results source-id`}</code>
            </pre>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Referencia del SDK de Python</h2>
            <p className="text-muted-foreground mb-4">
              Para perfilado programático, puedes usar el SDK de Python:
            </p>
            
            <pre className="bg-muted p-4 rounded-lg mb-4">
              <code>{`from plexus import Plexus

plexus = Plexus(api_key="tu-api-key")

# Ejecutar un perfil en una fuente
profile = plexus.sources.profile(
    source_id="source-id",
    options={
        "content_analysis": True,
        "pattern_detection": True,
        "quality_metrics": True
    }
)

# Obtener resultados del perfil
results = profile.get_results()`}</code>
            </pre>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Próximamente</h2>
            <p className="text-muted-foreground">
              Se están desarrollando características adicionales de perfilado. Vuelve pronto para:
            </p>
            <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
              <li>Opciones avanzadas de visualización</li>
              <li>Plantillas de perfilado personalizadas</li>
              <li>Generación automatizada de insights</li>
              <li>Compartir perfiles y colaboración</li>
            </ul>
          </section>
        </div>
      </div>
    );
  }

  // English content (default)
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Profile a Source</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to analyze and profile your sources using the Plexus dashboard interface.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Profiling Sources in the Dashboard</h2>
          <p className="text-muted-foreground mb-4">
            Source profiling helps you understand the characteristics and patterns in your data
            before running evaluations. The dashboard provides comprehensive tools for analyzing
            your sources.
          </p>
          
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">Step-by-Step Guide</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Access Source Details:</strong>
                  <p>Navigate to your source in the Sources list and click on it to view details.</p>
                </li>
                <li>
                  <strong>Start Profiling:</strong>
                  <p>Click the "Profile Source" button in the source details view.</p>
                </li>
                <li>
                  <strong>Configure Analysis:</strong>
                  <p>Select the profiling options you want to run:</p>
                  <ul className="list-disc pl-6 mt-2 space-y-2">
                    <li>Content analysis</li>
                    <li>Pattern detection</li>
                    <li>Quality metrics</li>
                    <li>Custom analysis options</li>
                  </ul>
                </li>
                <li>
                  <strong>Run Profile:</strong>
                  <p>Click "Start Analysis" to begin the profiling process.</p>
                </li>
                <li>
                  <strong>Review Results:</strong>
                  <p>Once complete, examine the detailed profiling results in the dashboard.</p>
                </li>
              </ol>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Understanding Profile Results</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Content Analysis</h3>
              <p className="text-muted-foreground">
                View detailed breakdowns of your source content, including structure, format,
                and key characteristics. The dashboard presents this information through
                interactive visualizations and detailed reports.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Pattern Detection</h3>
              <p className="text-muted-foreground">
                Explore identified patterns and anomalies through the dashboard's pattern
                analysis view. This helps you understand common themes and potential issues
                in your content.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Quality Metrics</h3>
              <p className="text-muted-foreground">
                Review comprehensive quality measurements through intuitive charts and
                detailed metric breakdowns in the dashboard interface.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Profile Management Tips</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Saving Profiles</h3>
              <p className="text-muted-foreground">
                Save profile configurations as templates for quick reuse across multiple sources.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Comparing Results</h3>
              <p className="text-muted-foreground">
                Use the dashboard's comparison view to analyze profile results across different
                sources or time periods.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Using the CLI</h2>
          <p className="text-muted-foreground mb-4">
            For automated profiling workflows, you can use the Plexus CLI:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`# Run a profile on a source
plexus sources profile source-id --analysis-type full

# Get profile results
plexus sources profile-results source-id`}</code>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Python SDK Reference</h2>
          <p className="text-muted-foreground mb-4">
            For programmatic profiling, you can use the Python SDK:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`from plexus import Plexus

plexus = Plexus(api_key="your-api-key")

# Run a profile on a source
profile = plexus.sources.profile(
    source_id="source-id",
    options={
        "content_analysis": True,
        "pattern_detection": True,
        "quality_metrics": True
    }
)

# Get profile results
results = profile.get_results()`}</code>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Additional profiling features are being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Advanced visualization options</li>
            <li>Custom profiling templates</li>
            <li>Automated insights generation</li>
            <li>Profile sharing and collaboration</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 