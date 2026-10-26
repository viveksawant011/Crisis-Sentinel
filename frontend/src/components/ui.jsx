export function Card({ title, subtitle, actions, children, footer, bodyClass = 'card-body', className = '' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <div>
            {title && <h2 className="card-title">{title}</h2>}
            {subtitle && <p className="card-sub">{subtitle}</p>}
          </div>
          {actions && <div className="card-head-actions">{actions}</div>}
        </header>
      )}
      {bodyClass ? <div className={bodyClass}>{children}</div> : children}
      {footer && <footer className="card-foot">{footer}</footer>}
    </section>
  )
}

export function Badge({ tone = 'neutral', dot = false, children, title }) {
  return (
    <span className={`badge tone-${tone}`} title={title}>
      {dot && <span className="dot" aria-hidden="true" />}
      {children}
    </span>
  )
}

export function Alert({ tone = 'info', title, children, onClose }) {
  return (
    <div className={`alert alert-${tone}`} role={tone === 'danger' ? 'alert' : 'status'}>
      <div className="alert-body">
        {title && <strong>{title} </strong>}
        {children}
      </div>
      {onClose && (
        <button type="button" className="alert-close" onClick={onClose} aria-label="Dismiss">
          ×
        </button>
      )}
    </div>
  )
}

export function Spinner() {
  return <span className="spinner" aria-hidden="true" />
}
