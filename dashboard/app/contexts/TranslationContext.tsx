"use client";

import React, { createContext, useContext, ReactNode } from 'react';

interface TranslationContextType {
  t: (key: string, variables?: Record<string, any>) => string;
  locale: string;
}

const TranslationContext = createContext<TranslationContextType | undefined>(undefined);

interface TranslationProviderProps {
  children: ReactNode;
  messages: Record<string, any>;
  locale: string;
}

export function TranslationProvider({ children, messages, locale }: TranslationProviderProps) {
  const t = (key: string, variables?: Record<string, any>): string => {
    const keys = key.split('.');
    let value = messages;
    
    for (const k of keys) {
      if (value && typeof value === 'object' && k in value) {
        value = value[k];
      } else {
        return key; // Return key if translation not found
      }
    }
    
    let result = typeof value === 'string' ? value : key;
    
    // Handle variable interpolation
    if (variables && typeof result === 'string') {
      Object.keys(variables).forEach(varKey => {
        const placeholder = `{${varKey}}`;
        result = result.replace(new RegExp(placeholder, 'g'), String(variables[varKey]));
      });
    }
    
    return result;
  };

  return (
    <TranslationContext.Provider value={{ t, locale }}>
      {children}
    </TranslationContext.Provider>
  );
}

export function useTranslations(namespace?: string) {
  const context = useContext(TranslationContext);
  if (!context) {
    throw new Error('useTranslations must be used within a TranslationProvider');
  }

  return (key: string, variables?: Record<string, any>) => {
    const fullKey = namespace ? `${namespace}.${key}` : key;
    return context.t(fullKey, variables);
  };
}

export function useLocale() {
  const context = useContext(TranslationContext);
  if (!context) {
    throw new Error('useLocale must be used within a TranslationProvider');
  }
  return context.locale;
}

export function useTranslationContext() {
  const context = useContext(TranslationContext);
  if (!context) {
    throw new Error('useTranslationContext must be used within a TranslationProvider');
  }
  return context;
}