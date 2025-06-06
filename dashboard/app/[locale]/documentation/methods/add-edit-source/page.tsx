'use client';

import { useTranslationContext } from '@/app/contexts/TranslationContext'

export default function AddEditSourcePage() {
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">Agregar/Editar una Fuente</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Aprende cómo crear y gestionar fuentes en Plexus usando la interfaz del Panel de Control.
        </p>

        <div className="space-y-8">
          <section>
            <h2 className="text-2xl font-semibold mb-4">Agregar una Fuente en el Panel de Control</h2>
            <p className="text-muted-foreground mb-4">
              El Panel de Control de Plexus proporciona una interfaz intuitiva para crear y gestionar tus fuentes.
              Sigue estos pasos para agregar una nueva fuente:
            </p>
            
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-medium mb-3">Guía Paso a Paso</h3>
                <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                  <li>
                    <strong>Navegar a Fuentes:</strong>
                    <p>Haz clic en "Fuentes" en el menú de navegación principal para acceder a la página de gestión de fuentes.</p>
                  </li>
                  <li>
                    <strong>Crear Nueva Fuente:</strong>
                    <p>Haz clic en el botón "Agregar Fuente" en la esquina superior derecha de la página.</p>
                  </li>
                  <li>
                    <strong>Elegir Tipo de Fuente:</strong>
                    <p>Selecciona el tipo de fuente que deseas crear (ej. Texto, Audio).</p>
                  </li>
                  <li>
                    <strong>Configurar Ajustes:</strong>
                    <p>Completa la información requerida:</p>
                    <ul className="list-disc pl-6 mt-2 space-y-2">
                      <li>Nombre de la fuente</li>
                      <li>Descripción (opcional)</li>
                      <li>Contenido o carga de archivo</li>
                      <li>Ajustes adicionales específicos al tipo de fuente</li>
                    </ul>
                  </li>
                  <li>
                    <strong>Guardar:</strong>
                    <p>Haz clic en "Crear" para guardar tu nueva fuente.</p>
                  </li>
                </ol>
              </div>

              <div>
                <h3 className="text-xl font-medium mb-3">Editar una Fuente Existente</h3>
                <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                  <li>
                    <strong>Localizar la Fuente:</strong>
                    <p>Encuentra la fuente que deseas editar en la lista de Fuentes.</p>
                  </li>
                  <li>
                    <strong>Acceder al Modo de Edición:</strong>
                    <p>Haz clic en el ícono de edición (lápiz) junto al nombre de la fuente.</p>
                  </li>
                  <li>
                    <strong>Realizar Cambios:</strong>
                    <p>Actualiza la información de la fuente según sea necesario.</p>
                  </li>
                  <li>
                    <strong>Guardar Cambios:</strong>
                    <p>Haz clic en "Guardar" para aplicar tus actualizaciones.</p>
                  </li>
                </ol>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Consejos de Gestión de Fuentes</h2>
            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-medium mb-2">Organización</h3>
                <p className="text-muted-foreground">
                  Usa nombres claros y descriptivos junto con etiquetas opcionales para mantener tus fuentes organizadas
                  y fácilmente buscables.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-medium mb-2">Operaciones por Lote</h3>
                <p className="text-muted-foreground">
                  Selecciona múltiples fuentes para realizar operaciones por lote como eliminación o actualización de etiquetas.
                </p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Usar la CLI</h2>
            <p className="text-muted-foreground mb-4">
              Para automatización y scripts, puedes usar la CLI de Plexus para gestionar fuentes:
            </p>
            
            <pre className="bg-muted p-4 rounded-lg mb-4">
              <code>{`# Crear una nueva fuente
plexus sources create --name "Mi Fuente" --type text --content "Contenido de ejemplo"

# Actualizar una fuente existente
plexus sources update source-id --name "Nombre Actualizado" --content "Contenido actualizado"`}</code>
            </pre>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Referencia del SDK de Python</h2>
            <p className="text-muted-foreground mb-4">
              Para acceso programático, puedes usar el SDK de Python:
            </p>
            
            <pre className="bg-muted p-4 rounded-lg mb-4">
              <code>{`from plexus import Plexus

plexus = Plexus(api_key="tu-api-key")

# Crear una nueva fuente
source = plexus.sources.create(
    name="Mi Fuente",
    type="text",
    data="Contenido de ejemplo"
)

# Actualizar una fuente existente
source = plexus.sources.update(
    source_id="source-id",
    name="Nombre de Fuente Actualizado",
    data="Contenido actualizado"
)`}</code>
            </pre>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Próximamente</h2>
            <p className="text-muted-foreground">
              Se están desarrollando documentación y características adicionales. Vuelve pronto para:
            </p>
            <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
              <li>Técnicas avanzadas de gestión de fuentes</li>
              <li>Capacidades de importación/exportación masiva</li>
              <li>Plantillas de fuentes personalizadas</li>
              <li>Ejemplos de integración</li>
            </ul>
          </section>
        </div>
      </div>
    );
  }

  // English content (default)
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Add/Edit a Source</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to create and manage sources in Plexus using the dashboard interface.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Adding a Source in the Dashboard</h2>
          <p className="text-muted-foreground mb-4">
            The Plexus dashboard provides an intuitive interface for creating and managing your sources.
            Follow these steps to add a new source:
          </p>
          
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">Step-by-Step Guide</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Navigate to Sources:</strong>
                  <p>Click on "Sources" in the main navigation menu to access the sources management page.</p>
                </li>
                <li>
                  <strong>Create New Source:</strong>
                  <p>Click the "Add Source" button in the top-right corner of the page.</p>
                </li>
                <li>
                  <strong>Choose Source Type:</strong>
                  <p>Select the type of source you want to create (e.g., Text, Audio).</p>
                </li>
                <li>
                  <strong>Configure Settings:</strong>
                  <p>Fill in the required information:</p>
                  <ul className="list-disc pl-6 mt-2 space-y-2">
                    <li>Source name</li>
                    <li>Description (optional)</li>
                    <li>Content or file upload</li>
                    <li>Additional settings specific to the source type</li>
                  </ul>
                </li>
                <li>
                  <strong>Save:</strong>
                  <p>Click "Create" to save your new source.</p>
                </li>
              </ol>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">Editing an Existing Source</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Locate the Source:</strong>
                  <p>Find the source you want to edit in the Sources list.</p>
                </li>
                <li>
                  <strong>Access Edit Mode:</strong>
                  <p>Click the edit icon (pencil) next to the source name.</p>
                </li>
                <li>
                  <strong>Make Changes:</strong>
                  <p>Update the source's information as needed.</p>
                </li>
                <li>
                  <strong>Save Changes:</strong>
                  <p>Click "Save" to apply your updates.</p>
                </li>
              </ol>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Source Management Tips</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Organization</h3>
              <p className="text-muted-foreground">
                Use clear, descriptive names and optional tags to keep your sources organized
                and easily searchable.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Batch Operations</h3>
              <p className="text-muted-foreground">
                Select multiple sources to perform batch operations like deletion or tag updates.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Using the CLI</h2>
          <p className="text-muted-foreground mb-4">
            For automation and scripting, you can use the Plexus CLI to manage sources:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`# Create a new source
plexus sources create --name "My Source" --type text --content "Sample content"

# Update an existing source
plexus sources update source-id --name "Updated Name" --content "Updated content"`}</code>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Python SDK Reference</h2>
          <p className="text-muted-foreground mb-4">
            For programmatic access, you can use the Python SDK:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`from plexus import Plexus

plexus = Plexus(api_key="your-api-key")

# Create a new source
source = plexus.sources.create(
    name="My Source",
    type="text",
    data="Sample content"
)

# Update an existing source
source = plexus.sources.update(
    source_id="source-id",
    name="Updated Source Name",
    data="Updated content"
)`}</code>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Additional documentation and features are being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Advanced source management techniques</li>
            <li>Bulk import/export capabilities</li>
            <li>Custom source templates</li>
            <li>Integration examples</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 