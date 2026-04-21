import React from "react";

type State = {
  error: Error | null;
};

export class RootErrorBoundary extends React.Component<React.PropsWithChildren, State> {
  state: State = {
    error: null,
  };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error("Root render error:", error);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-6">
          <div className="w-full max-w-2xl rounded-2xl border bg-card p-6 shadow-sm">
            <p className="text-sm font-semibold text-destructive">Application Error</p>
            <h1 className="mt-2 text-2xl font-semibold">The app failed to render.</h1>
            <pre className="mt-4 overflow-auto rounded-xl bg-muted p-4 text-sm whitespace-pre-wrap break-words">
              {this.state.error.message}
            </pre>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
