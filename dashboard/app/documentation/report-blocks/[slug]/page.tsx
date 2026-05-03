import { notFound } from "next/navigation";

import ReportDocPage from "../report-doc-page";
import { reportDocBySlug, reportDocs } from "../report-docs-data";

export function generateStaticParams() {
  return reportDocs.map((doc) => ({ slug: doc.slug }));
}

export default async function DynamicReportDocPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const doc = reportDocBySlug[slug];
  if (!doc) notFound();
  return <ReportDocPage doc={doc} />;
}
