"use client";

import { useState, useEffect } from "react";
import { generateClient } from "aws-amplify/data";
import type { Schema } from "@/amplify/data/resource";
import { Amplify } from "aws-amplify";
import outputs from "@/amplify_outputs.json";
import { Authenticator, useAuthenticator } from '@aws-amplify/ui-react'
import '@aws-amplify/ui-react/styles.css';
import { config } from '@fortawesome/fontawesome-svg-core'
import '@fortawesome/fontawesome-svg-core/styles.css'
config.autoAddCss = false

Amplify.configure(outputs);

import DashboardLayout from '../components/dashboard-layout'
import SquareLogo, { LogoVariant } from '../components/logo-square'
import ActivityDashboard from '../components/activity-dashboard'

const client = generateClient<Schema>();

function AppContent({ signOut }: { signOut: () => void }) {
  const [todos, setTodos] = useState<Array<Schema["Todo"]["type"]>>([]);

  function listTodos() {
    client.models.Todo.observeQuery().subscribe({
      next: (data) => setTodos([...data.items]),
    });
  }

  useEffect(() => {
    listTodos();
  }, []);

  function createTodo() {
    client.models.Todo.create({
      content: window.prompt("Todo content"),
    });
  }
  
  function deleteTodo(id: string) {
    client.models.Todo.delete({ id })
  }

  return (
    <DashboardLayout signOut={signOut}>
      <ActivityDashboard />
    </DashboardLayout>
  );
}

function AuthenticatedApp() {
  const { authStatus, signOut } = useAuthenticator(context => [context.authStatus, context.user]);

  if (authStatus !== 'authenticated') {
    return (
      <div className="flex flex-col md:flex-row items-center justify-center min-h-screen gap-4 bg-[hsl(var(--light-blue-bg))]">
        <div className="w-full max-w-md">
          <SquareLogo variant={LogoVariant.Square} />
        </div>
        <div className="w-full max-w-md">
          <Authenticator />
        </div>
      </div>
    );
  }

  return <AppContent signOut={signOut} />;
}

export default function App() {
  return (
    <Authenticator.Provider>
      <AuthenticatedApp />
    </Authenticator.Provider>
  );
}