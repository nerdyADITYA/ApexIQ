import { Component } from 'react'

/** Catches render errors (e.g. WebGL unavailable) so one failing widget does not blank the page. */
export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div role="alert" className="card error">
          {this.props.message ?? 'Something went wrong.'}
          <div className="muted small">{String(this.state.error.message ?? this.state.error)}</div>
        </div>
      )
    }
    return this.props.children
  }
}
