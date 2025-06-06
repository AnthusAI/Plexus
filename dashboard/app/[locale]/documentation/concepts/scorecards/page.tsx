'use client';

import { Button as DocButton } from "@/components/ui/button"
import { useTranslationContext } from '@/app/contexts/TranslationContext'
import Link from "next/link"

export default function ScorecardsPage() {
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">Cuadros de Puntuación</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Comprende cómo crear y gestionar Cuadros de Puntuación para evaluar tu contenido de manera efectiva.
        </p>

        <div className="space-y-8">
          <section>
            <h2 className="text-2xl font-semibold mb-4">¿Qué son los Cuadros de Puntuación?</h2>
            <p className="text-muted-foreground mb-4">
              Los Cuadros de Puntuación son colecciones de criterios de evaluación que definen cómo debe
              analizarse tu contenido. Ayudan a asegurar una evaluación consistente en todas tus fuentes
              proporcionando un marco estructurado para la evaluación.
            </p>
            <p className="text-muted-foreground mb-4">
              Piensa en un cuadro de puntuación como una plantilla de evaluación integral que contiene todas las 
              métricas y criterios que deseas medir para un tipo específico de contenido. Los Cuadros de Puntuación 
              pueden adaptarse a diferentes tipos de contenido, objetivos comerciales o estándares de calidad.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Estructura del Cuadro de Puntuación</h2>
            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-medium mb-2">Secciones</h3>
                <p className="text-muted-foreground mb-4">
                  Los Cuadros de Puntuación se organizan en secciones lógicas que agrupan criterios de evaluación relacionados.
                  Por ejemplo, un cuadro de puntuación de servicio al cliente podría tener secciones para "Saludo", "Resolución de Problemas",
                  y "Cierre".
                </p>
              </div>
              
              <div>
                <h3 className="text-xl font-medium mb-2">Puntuaciones</h3>
                <p className="text-muted-foreground mb-4">
                  Criterios de evaluación individuales que evalúan aspectos específicos de tu contenido.
                  Cada puntuación puede personalizarse con su propia lógica de evaluación y requisitos.
                  Las puntuaciones son los bloques de construcción de tu marco de evaluación.
                </p>
                <p className="text-muted-foreground mb-4">
                  Ejemplos de puntuaciones incluyen:
                </p>
                <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                  <li>Precisión gramatical y ortográfica</li>
                  <li>Análisis de sentimiento (positivo/negativo/neutral)</li>
                  <li>Cumplimiento de regulaciones específicas</li>
                  <li>Presencia de información requerida</li>
                  <li>Métricas específicas del negocio personalizadas</li>
                </ul>
              </div>
              
              <div>
                <h3 className="text-xl font-medium mb-2">Secciones</h3>
                <p className="text-muted-foreground">
                  Agrupaciones lógicas de puntuaciones relacionadas dentro de un cuadro de puntuación. Las secciones ayudan a organizar
                  las puntuaciones en categorías para una mejor gestión y comprensión.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-medium mb-2">Pesos</h3>
                <p className="text-muted-foreground mb-4">
                  Factores de importancia que determinan cuánto contribuye cada puntuación al
                  resultado general de la evaluación. Los pesos te permiten priorizar ciertos criterios
                  sobre otros basándote en su importancia para tus objetivos comerciales.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-medium mb-2">Versiones</h3>
                <p className="text-muted-foreground">
                  Las configuraciones de puntuación tienen versiones, permitiéndote rastrear cambios a lo largo del tiempo,
                  comparar diferentes implementaciones y promover versiones específicas al estado de campeón.
                </p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Gestión por CLI</h2>
            <p className="text-muted-foreground mb-4">
              El CLI de Plexus proporciona comandos poderosos para gestionar cuadros de puntuación:
            </p>
            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-medium mb-2">Listar Cuadros de Puntuación</h3>
                <pre className="bg-muted p-4 rounded-lg mb-4">
                  <code>{`# Listar todos los cuadros de puntuación para una cuenta
plexus scorecards list "nombre-cuenta"

# Listar con filtrado
plexus scorecards list "nombre-cuenta" --name "Nombre del Cuadro"
plexus scorecards list "nombre-cuenta" --key "clave-cuadro"

# Opciones de rendimiento
plexus scorecards list "nombre-cuenta" --fast  # Omitir obtener puntuaciones para resultados más rápidos
plexus scorecards list "nombre-cuenta" --hide-scores  # No mostrar puntuaciones en la salida`}</code>
                </pre>
                <p className="text-muted-foreground">
                  El comando list usa una consulta GraphQL optimizada para obtener cuadros de puntuación, secciones, 
                  y puntuaciones en una sola solicitud, proporcionando un rendimiento significativamente más rápido.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-medium mb-2">Ver Detalles de Puntuación</h3>
                <pre className="bg-muted p-4 rounded-lg mb-4">
                  <code>{`# Ver una puntuación específica por nombre, clave, ID, o ID externo
plexus scorecards score "Nombre de Puntuación" --account "nombre-cuenta"
plexus scorecards score "clave-puntuacion" --account "nombre-cuenta"
plexus scorecards score "id-puntuacion" --show-versions --show-config

# Acotar a un cuadro de puntuación específico
plexus scorecards score "Nombre de Puntuación" --scorecard "Nombre del Cuadro"`}</code>
                </pre>
              </div>
              <div>
                <h3 className="text-xl font-medium mb-2">Listar Puntuaciones en un Cuadro</h3>
                <p className="text-muted-foreground mb-4">
                  Para listar todas las puntuaciones dentro de un cuadro de puntuación, usa el comando <code>scores list</code>:
                </p>
                <pre className="bg-muted p-4 rounded-lg mb-4">
                  <code>{`# Listar todas las puntuaciones en un cuadro de puntuación
plexus scores list --scorecard "Nombre del Cuadro"

# También puedes usar la forma singular
plexus score list --scorecard "Nombre del Cuadro"`}</code>
                </pre>
                <p className="text-muted-foreground">
                  Este comando muestra todas las puntuaciones organizadas por sección, incluyendo sus IDs, claves, e IDs externos.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-medium mb-2">Gestión de Versiones</h3>
                <pre className="bg-muted p-4 rounded-lg mb-4">
                  <code>{`# Ver historial de versiones (próximamente)
plexus scorecards history --account-key "clave-cuenta" --score-key "clave-puntuacion"

# Promover una versión a campeón (próximamente)
plexus scorecards promote --account-key "clave-cuenta" --score-id "id-puntuacion" --version-id "id-version"

# Obtener últimas versiones campeón (próximamente)
plexus scorecards pull --account-key "clave-cuenta"

# Enviar cambios locales como nuevas versiones
plexus scorecards push --scorecard "nombre-cuadro" --note "Configuración actualizada"`}</code>
                </pre>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Mejores Prácticas</h2>
            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-medium mb-2">Organización de Cuadros de Puntuación</h3>
                <p className="text-muted-foreground">
                  Agrupa puntuaciones relacionadas en secciones lógicas para mejorar claridad y mantenibilidad.
                  Usa convenciones de nomenclatura consistentes para cuadros de puntuación, secciones y puntuaciones.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-medium mb-2">Gestión de Versiones</h3>
                <p className="text-muted-foreground">
                  Agrega notas descriptivas a nuevas versiones para documentar cambios. Prueba nuevas versiones
                  exhaustivamente antes de promoverlas al estado de campeón.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-medium mb-2">Consideraciones de Rendimiento</h3>
                <p className="text-muted-foreground">
                  Usa la opción <code>--fast</code> cuando listes muchos cuadros de puntuación para mejorar el rendimiento.
                  Esto omite obtener detalles de puntuación cuando solo necesitas información básica del cuadro.
                </p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Próximamente</h2>
            <p className="text-muted-foreground">
              Se están desarrollando características adicionales para cuadros de puntuación. Vuelve pronto para:
            </p>
            <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
              <li>Opciones avanzadas de configuración de puntuación</li>
              <li>Características de edición colaborativa</li>
              <li>Análisis de rendimiento</li>
              <li>Operaciones masivas para gestión de cuadros de puntuación</li>
            </ul>
          </section>
        </div>
      </div>
    );
  }

  // English content (default)
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Scorecards</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Understand how to create and manage Scorecards to evaluate your content effectively.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">What are Scorecards?</h2>
          <p className="text-muted-foreground mb-4">
            Scorecards are collections of evaluation criteria that define how your content
            should be analyzed. They help ensure consistent evaluation across all your sources
            by providing a structured framework for assessment.
          </p>
          <p className="text-muted-foreground mb-4">
            Think of a scorecard as a comprehensive evaluation template that contains all the 
            metrics and criteria you want to measure for a specific type of content. Scorecards 
            can be tailored to different content types, business objectives, or quality standards.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Scorecard Structure</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Sections</h3>
              <p className="text-muted-foreground mb-4">
                Scorecards are organized into logical sections that group related evaluation criteria.
                For example, a customer service scorecard might have sections for "Greeting", "Problem Resolution",
                and "Closing".
              </p>
            </div>
            
            <div>
              <h3 className="text-xl font-medium mb-2">Scores</h3>
              <p className="text-muted-foreground mb-4">
                Individual evaluation criteria that assess specific aspects of your content.
                Each score can be customized with its own evaluation logic and requirements.
                Scores are the building blocks of your evaluation framework.
              </p>
              <p className="text-muted-foreground mb-4">
                Examples of scores include:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>Grammar and spelling accuracy</li>
                <li>Sentiment analysis (positive/negative/neutral)</li>
                <li>Compliance with specific regulations</li>
                <li>Presence of required information</li>
                <li>Custom business-specific metrics</li>
              </ul>
            </div>
            
            <div>
              <h3 className="text-xl font-medium mb-2">Sections</h3>
              <p className="text-muted-foreground">
                Logical groupings of related scores within a scorecard. Sections help organize
                scores into categories for better management and understanding.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Weights</h3>
              <p className="text-muted-foreground mb-4">
                Importance factors that determine how much each score contributes to the
                overall evaluation result. Weights allow you to prioritize certain criteria
                over others based on their importance to your business objectives.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Versions</h3>
              <p className="text-muted-foreground">
                Score configurations are versioned, allowing you to track changes over time,
                compare different implementations, and promote specific versions to champion status.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">CLI Management</h2>
          <p className="text-muted-foreground mb-4">
            The Plexus CLI provides powerful commands for managing scorecards:
          </p>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Listing Scorecards</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# List all scorecards for an account
plexus scorecards list "account-name"

# List with filtering
plexus scorecards list "account-name" --name "Scorecard Name"
plexus scorecards list "account-name" --key "scorecard-key"

# Performance options
plexus scorecards list "account-name" --fast  # Skip fetching scores for faster results
plexus scorecards list "account-name" --hide-scores  # Don't display scores in output`}</code>
              </pre>
              <p className="text-muted-foreground">
                The list command uses an optimized single GraphQL query to fetch scorecards, sections, 
                and scores in one request, providing significantly faster performance.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Viewing Score Details</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# View a specific score by name, key, ID, or external ID
plexus scorecards score "Score Name" --account "account-name"
plexus scorecards score "score-key" --account "account-name"
plexus scorecards score "score-id" --show-versions --show-config

# Scope to a specific scorecard
plexus scorecards score "Score Name" --scorecard "Scorecard Name"`}</code>
              </pre>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Listing Scores in a Scorecard</h3>
              <p className="text-muted-foreground mb-4">
                To list all scores within a scorecard, use the <code>scores list</code> command:
              </p>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# List all scores in a scorecard
plexus scores list --scorecard "Scorecard Name"

# You can also use the singular form
plexus score list --scorecard "Scorecard Name"`}</code>
              </pre>
              <p className="text-muted-foreground">
                This command displays all scores organized by section, including their IDs, keys, and external IDs.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Version Management</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# View version history (coming soon)
plexus scorecards history --account-key "account-key" --score-key "score-key"

# Promote a version to champion (coming soon)
plexus scorecards promote --account-key "account-key" --score-id "score-id" --version-id "version-id"

# Pull latest champion versions (coming soon)
plexus scorecards pull --account-key "account-key"

# Push local changes as new versions
plexus scorecards push --scorecard "scorecard-name" --note "Updated configuration"`}</code>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Best Practices</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Scorecard Organization</h3>
              <p className="text-muted-foreground">
                Group related scores into logical sections to improve clarity and maintainability.
                Use consistent naming conventions for scorecards, sections, and scores.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Version Management</h3>
              <p className="text-muted-foreground">
                Add descriptive notes to new versions to document changes. Test new versions
                thoroughly before promoting them to champion status.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Performance Considerations</h3>
              <p className="text-muted-foreground">
                Use the <code>--fast</code> option when listing many scorecards to improve performance.
                This skips fetching score details when you only need basic scorecard information.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Additional scorecard features are being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Advanced score configuration options</li>
            <li>Collaborative editing features</li>
            <li>Performance analytics</li>
            <li>Bulk operations for scorecard management</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 