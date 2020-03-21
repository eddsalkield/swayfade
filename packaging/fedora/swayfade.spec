Name:		swayfade
Version:	0.0.1
Release:        1%{?dist}
Summary:	Fades unfocussed windows, for sway and i3

License:	GPLv3
URL:		https://github.com/eddsalkield/sway-fade
Source0:	%{name}-%{version}.tar.gz

BuildRoot:	%{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix:		%{_prefix}
BuildArch:	noarch
Vendor:		Edd Salkield <edd@salkield.uk>

Requires:	python3 python3-pyxdg python3-toml

%description
Fades unfocussed windows, for sway and i3


%prep
%setup -n %{name}-%{version} -n %{name}-%{version}


%build
python3 setup.py build

%install
python3 setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root)


%changelog
* Sat Mar 21 2020 Edd Salkield <edd@salkield.uk> - 0.0.1-1
