function ErrorBanner({ message }) {
  return (
    <div className="banner error">
      <strong>Analysis failed.</strong> {message}
    </div>
  )
}

export default ErrorBanner