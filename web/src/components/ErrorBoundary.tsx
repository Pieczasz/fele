import { Component, type ErrorInfo, type ReactNode } from 'react'

/** One broken view must not blank the whole app: show what failed and keep the navigation working. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  override state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  override componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info.componentStack)
  }

  override render() {
    if (this.state.error) {
      return (
        <div role="alert" className="space-y-2 rounded border border-bad p-4">
          <h1 className="text-xl font-bold">This view hit an error</h1>
          <p className="text-sm text-muted">{this.state.error.message}</p>
          <p className="text-sm text-muted">Other pages still work; pick one above, or reload this one.</p>
        </div>
      )
    }
    return this.props.children
  }
}
