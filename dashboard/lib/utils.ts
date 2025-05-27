import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import * as yaml from 'js-yaml'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Parse output string that could be either YAML or JSON format
 * @param output - The output string to parse
 * @returns Parsed object or the original string if parsing fails
 */
export function parseOutputString(output: any): Record<string, any> {
  if (typeof output === 'string') {
    try {
      // First try JSON parsing
      return JSON.parse(output);
    } catch (jsonError) {
      // If JSON parsing fails, try YAML parsing
      try {
        const parsedYaml = yaml.load(output);
        // Ensure we return an object
        if (parsedYaml && typeof parsedYaml === 'object') {
          return parsedYaml as Record<string, any>;
        }
        // If YAML parsed to a primitive, wrap it
        return { value: parsedYaml };
      } catch (yamlError) {
        console.error('Failed to parse output as JSON or YAML:', { jsonError, yamlError });
        return { error: 'Failed to parse output', raw: output };
      }
    }
  }
  
  if (output && typeof output === 'object') {
    return output;
  }
  
  return {};
}
