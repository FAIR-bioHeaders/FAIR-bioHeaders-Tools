process FAIRBIOHEADERS_COMBINE {
    tag "${meta.id}"
    label 'process_single'

    conda "${moduleDir}/environment.yml"
    // Interim: the FAIR-bioHeaders image (built from the released wheel). Replace with the
    // Seqera/BioContainers URLs from `nf-core modules containers create` once
    // bioconda::fair-bioheaders is published.
    container "${workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container
        ? 'docker://ghcr.io/fair-bioheaders/fair-bioheaders:0.5.0'
        : 'ghcr.io/fair-bioheaders/fair-bioheaders:0.5.0'}"

    input:
    tuple val(meta), path(metadata), path(sequence)

    output:
    tuple val(meta), path("${prefix}.fhr.*"), emit: sequence
    tuple val("${task.process}"), val('fair-bioheaders'), eval("bioheaders --version"), emit: versions_fairbioheaders, topic: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    prefix = task.ext.prefix ?: "${meta.id}"
    def type = sequence.name ==~ /.*\.gfa(\.b?gz)?$/ ? 'gfa' : 'fasta'
    def extension = (type == 'gfa' ? 'gfa' : 'fa') + (sequence.name ==~ /.*\.b?gz$/ ? '.gz' : '')
    """
    bioheaders combine \\
        --type ${type} \\
        ${args} \\
        --output '${prefix}.fhr.${extension}' \\
        '${metadata}' \\
        '${sequence}'
    """

    stub:
    prefix = task.ext.prefix ?: "${meta.id}"
    def type = sequence.name ==~ /.*\.gfa(\.b?gz)?$/ ? 'gfa' : 'fasta'
    def extension = (type == 'gfa' ? 'gfa' : 'fa')
    def output = sequence.name ==~ /.*\.b?gz$/
        ? "echo '' | gzip > '${prefix}.fhr.${extension}.gz'"
        : "touch '${prefix}.fhr.${extension}'"
    """
    ${output}
    """
}
