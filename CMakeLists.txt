project(SMQTK)
cmake_minimum_required(VERSION 2.8)


###
# Versioning -- parsed from central file
#
# Expected format: <major>.<minor>.<patch>
#
file(READ "${SMQTK_SOURCE_DIR}/VERSION" SMQTK_VERSION)
string( STRIP "${SMQTK_VERSION}" SMQTK_VERSION )
string( REGEX MATCHALL "([0-9]+)(.([0-9]+))?(.([0-9]+))?" SMQTK_VERSION_MATCH "${SMQTK_VERSION}" )
message( STATUS "SMQTK_VERSION : ${SMQTK_VERSION}" )
message( STATUS "        Major : ${CMAKE_MATCH_1}" )  # Major part
message( STATUS "        Minor : ${CMAKE_MATCH_3}" )  # minor
message( STATUS "        Patch : ${CMAKE_MATCH_5}" )  # patch
set(SMQTK_VERSION_MAJOR ${CMAKE_MATCH_1})
set(SMQTK_VERSION_MINOR ${CMAKE_MATCH_3})
set(SMQTK_VERSION_PATCH ${CMAKE_MATCH_5})


###
# Determine where to install python things in our install tree
#
find_package(PythonInterp REQUIRED)

execute_process(
  COMMAND "${PYTHON_EXECUTABLE}" -c "import distutils.sysconfig; print distutils.sysconfig.get_python_lib(prefix='')"
  RESULT_VARIABLE proc_success
  OUTPUT_VARIABLE python_site_packages
  )

if(NOT ${proc_success} EQUAL 0)
  message(FATAL_ERROR "Request for python site-packages location failed with error code: ${proc_success}")
else()
  string(STRIP "${python_site_packages}" python_site_packages)
  message(STATUS "Python site-packages sub-path: ${python_site_packages}")
endif()


###
# TPL
#
# local installation control variables
set(TPL_BUILD_PREFIX "${CMAKE_CURRENT_BINARY_DIR}/TPL/build")
set(TPL_LOCAL_INSTALL "${CMAKE_CURRENT_BINARY_DIR}/TPL/install")
set(TPL_PYTHON_SP "${TPL_LOCAL_INSTALL}/${python_site_packages}")
add_subdirectory( TPL )


###
# compiled components
#
add_subdirectory( src )


###
# File configuration
#
# Environment setup scripts
configure_file("${SMQTK_SOURCE_DIR}/setup_env.build.sh.in"
               "${SMQTK_BINARY_DIR}/setup_env.build.sh"
               @ONLY
               )
configure_file("${SMQTK_SOURCE_DIR}/setup_env.install.sh.in"
               "${SMQTK_BINARY_DIR}/setup_env.install.sh"
               @ONLY
               )


###
# System Installation
#
install(DIRECTORY   docs/
        DESTINATION share/doc/SMQTK
        )

install(FILES requirements.conda.txt
              requirements.pip.txt
        DESTINATION share/smqtk
        )

# Should only be required for users installing to a non-standard location
install(FILES "${SMQTK_BINARY_DIR}/setup_env.install.sh"
        DESTINATION .
        RENAME setup_smqtk.sh
        )

# This is probably not the correct way to be doing this, but when using CPack,
# make sure the CMAKE_INSTALL_PREFIX is clean before constructing packages. If
# it is not, you may drag in other content not intended for installation.
# TODO: Have to do something about the shebang modification that python does
#       when we start caring about CPack generation as local python executable
#       probably won't match what a user has when installing.
install(
  CODE "execute_process( COMMAND ${PYTHON_EXECUTABLE} -m pip install --prefix=${CMAKE_INSTALL_PREFIX} .
                         WORKING_DIRECTORY ${SMQTK_SOURCE_DIR} )"
  )
# Repeat install directories containing content generated by the above python
# install step. This probably isn't the correct thing to do, but this at least
# registers the pip-installed files. Maybe the correct thing to do is to have
# the setup.py perform a CMake config/build/install run and control
# installation rules here instead (which would mean dumping the standard rules
# defined in setuptools).
install(
  DIRECTORY   ${CMAKE_INSTALL_PREFIX}/bin
              ${CMAKE_INSTALL_PREFIX}/lib
  DESTINATION .
  )


###
# CPack stuff
#

# TODO: Define system package dependencies here
set(SMQTK_DEPS "")

set( CPACK_PACKAGE_NAME "SMQTK" )
set( CPACK_PACKAGE_VENDOR "Kitware, Inc." )
set( CPACK_PACKAGE_CONTACT "smqtk-developers@kitware.com" )
set( CPACK_PACKAGE_VERSION_MAJOR ${SMQTK_VERSION_MAJOR} )
set( CPACK_PACKAGE_VERSION_MINOR ${SMQTK_VERSION_MINOR} )
set( CPACK_PACKAGE_VERSION_PATCH ${SMQTK_VERSION_PATCH} )
set( CPACK_PACKAGE_VERSION       ${SMQTK_VERSION} )
set( CPACK_PACKAGE_DESCRIPTION_FILE ${SMQTK_SOURCE_DIR}/README.md )
set( CPACK_PACKAGE_DESCRIPTION_SUMMARY "Python toolkit for pluggable algorithms and data structures for multimedia-based machine learning" )
set( CPACK_RESOURCE_FILE_LICENSE ${SMQTK_SOURCE_DIR}/LICENSE.txt )
set( CPACK_RESOURCE_FILE_READNE  ${SMQTK_SOURCE_DIR}/README.md )

if(EXISTS /etc/redhat-release)
  file(READ /etc/redhat-release RHEL_VERSION)
  string(REGEX REPLACE ".*release ([^\\. ]*).*" "\\1" RHEL_VERSION "${RHEL_VERSION}")
  set(CPACK_SYSTEM_NAME "el${RHEL_VERSION}.${CMAKE_SYSTEM_PROCESSOR}")
  set(CPACK_RPM_PACKAGE_AUTOREQPROV "no")
  set(CPACK_RPM_PACKAGE_REQUIRES "${SMQTK_DEPS}")
  set(CPACK_RPM_PACKAGE_RELOCATABLE TRUE)
else()
  set(CPACK_SYSTEM_NAME "${CMAKE_SYSTEM_NAME}-${CMAKE_SYSTEM_PROCESSOR}")
endif()

# DEFAULT
#set(CPACK_PACKAGE_FILE_NAME "${CPACK_PACKAGE_NAME}-${CPACK_PACKAGE_VERSION}-${CPACK_SYSTEM_NAME}")

include(CPack)
